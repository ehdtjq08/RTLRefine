"""Create and seal a synthetic dataset before any repair-model calls."""
import json
import random
from pathlib import Path

from rtl_agent.common import ROOT, sha256, write_json

DATA = ROOT / "mutation_cases/stream_buffer"
AUTHOR = ROOT / "research/mutation_challenge_v1_author"

BODY = '''
localparam DEPTH = 1 << ADDR_WIDTH;
reg [DATA_WIDTH+1:0] mem [0:DEPTH-1];
reg [ADDR_WIDTH-1:0] wr_ptr = 0;
reg [ADDR_WIDTH-1:0] rd_ptr = 0;
reg [ADDR_WIDTH:0] count = 0;

assign m_valid = !rst && (count != 0);
assign s_ready = !rst && ((count < DEPTH) || (m_ready && m_valid));
assign {m_last, m_user, m_data} = mem[rd_ptr];
wire push = s_valid && s_ready;
wire pop = m_valid && m_ready;

always @(posedge clk) begin
    if (rst) begin
        wr_ptr <= 0;
        rd_ptr <= 0;
        count <= 0;
    end else begin
        if (push) begin
            mem[wr_ptr] <= {s_last, s_user, s_data};
        end
        if (push) wr_ptr <= wr_ptr + 1'b1;
        if (pop) rd_ptr <= rd_ptr + 1'b1;
        case ({push, pop})
            2'b10: count <= count + 1'b1;
            2'b01: count <= count - 1'b1;
            default: count <= count;
        endcase
    end
end
endmodule
'''

OPERATORS = {
    "write_without_acceptance": ("        if (push) begin\n            mem[wr_ptr]", "        if (s_valid) begin\n            mem[wr_ptr]"),
    "read_while_stalled": ("        if (pop) rd_ptr <=", "        if (m_valid) rd_ptr <="),
    "reset_tail_retained": ("        wr_ptr <= 0;", "        wr_ptr <= wr_ptr;"),
    "over_accept_when_full": ("(count < DEPTH)", "(count <= DEPTH)"),
    "sideband_swap": ("mem[wr_ptr] <= {s_last, s_user, s_data};", "mem[wr_ptr] <= {s_user, s_last, s_data};"),
}


def main():
    AUTHOR.mkdir(exist_ok=False)
    folder = DATA / "cases"
    folder.mkdir(exist_ok=False)
    header = (DATA / "interface.vh").read_text()
    clean = header + BODY
    (AUTHOR / "clean.v").write_text(clean)
    (DATA / "COPYING").write_bytes((ROOT / "LICENSE").read_bytes())
    variants = [("clean_control", ()), ("equivalent_control", ())]
    variants += [(name, (name,)) for name in OPERATORS]
    variants += [("combined_write_and_reset", ("write_without_acceptance", "reset_tail_retained"))]
    rng = random.Random(20261023)
    rng.shuffle(variants)
    truth, public = [], []
    for number, (kind, operations) in enumerate(variants, 1):
        source = clean
        for name in operations:
            before, after = OPERATORS[name]
            if source.count(before) != 1:
                raise ValueError("Mutation must identify one exact original site")
            source = source.replace(before, after, 1)
        if kind == "equivalent_control":
            source = source.replace("default: count <= count;", "default: begin count <= count; end")
        case_id = f"candidate_{number:02d}"
        case_folder = folder / case_id
        case_folder.mkdir()
        (case_folder / "candidate.v").write_text(source)
        entry = {"case_id": case_id, "source": f"cases/{case_id}/candidate.v", "source_sha256": sha256(source.encode())}
        public.append(entry)
        truth.append({**entry, "kind": kind, "operators": operations, "injected_fault": bool(operations)})
    write_json(DATA / "dataset.json", {"schema": 1, "label": "Synthetic mutation challenge, not historical bugs",
               "seed": 20261023, "case_count": len(public), "cases": public,
               "contract_sha256": sha256((DATA / "contract.json").read_bytes()),
               "agent_context": "Each case is a separate API context. Faulted-case prompts exclude clean RTL, mutation map, operator names and source locations."})
    write_json(AUTHOR / "mutation_map.json", {"cases": truth, "clean_sha256": sha256(clean.encode()),
               "evaluation_only": True, "not_used_by_specification_checker": True})
    print({"cases": len(public), "injected_cases": sum(bool(ops) for _, ops in variants), "normal_controls": 2})


if __name__ == "__main__":
    main()
