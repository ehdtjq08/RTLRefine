"""Qualify a historical UART bit-order change using independent serial peers.

The unmodified historical pair can agree in loopback while disagreeing with an
LSB-first peer. This is a selected known upstream behavior change, not a newly
discovered defect or an introduced regression. The generic checker is unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rtl_agent.common import write_json, sha256
from rtl_agent.project_repair.project import load_project, archive_project
from rtl_agent.project_repair.workflow import run_project

CASE = ROOT / 'external_cases/uart_bitorder_external'

WRAPPER = '''// RTLRefine stateless packaging adapter, MIT. Vendor leaf headers are retained.
module uart_pair #(parameter DATA_WIDTH=8)(
 input wire clk,rst,
 input wire [DATA_WIDTH-1:0] tx_data,
 input wire tx_valid,
 output wire tx_ready,txd,tx_busy,
 input wire rxd,
 output wire [DATA_WIDTH-1:0] rx_data,
 output wire rx_valid,
 input wire rx_ready,
 output wire rx_busy,overrun_error,frame_error,
 input wire [15:0] prescale
);
uart_tx #(.DATA_WIDTH(DATA_WIDTH)) tx(.clk(clk),.rst(rst),
 .input_axi_tdata(tx_data),.input_axi_tvalid(tx_valid),.input_axi_tready(tx_ready),
 .txd(txd),.busy(tx_busy),.prescale(prescale));
uart_rx #(.DATA_WIDTH(DATA_WIDTH)) rx(.clk(clk),.rst(rst),
 .output_axi_tdata(rx_data),.output_axi_tvalid(rx_valid),.output_axi_tready(rx_ready),
 .rxd(rxd),.busy(rx_busy),.overrun_error(overrun_error),.frame_error(frame_error),.prescale(prescale));
endmodule
'''

BENCH = r'''`timescale 1ns/1ps
`include "rtlrefine_check.vh"
module TOP;
parameter DATA_WIDTH=8;
parameter PRESCALE=2;
parameter WORDS=3;
parameter SEED=32'h3741a9b3;
parameter LOOPBACK_ONLY=0;
parameter STRESS=0;
localparam BAUD=PRESCALE*8;
localparam MASK=(1<<DATA_WIDTH)-1;
reg clk=0,rst=0,tx_valid=0,rx_ready=1,peer_line=1,loopback=0;
reg [DATA_WIDTH-1:0] tx_data=0;
wire tx_ready,txd,tx_busy,rx_valid,rx_busy,overrun_error,frame_error;
wire [DATA_WIDTH-1:0] rx_data;
wire rxd=loopback ? txd : peer_line;
uart_pair #(.DATA_WIDTH(DATA_WIDTH)) dut(.clk(clk),.rst(rst),.tx_data(tx_data),
 .tx_valid(tx_valid),.tx_ready(tx_ready),.txd(txd),.tx_busy(tx_busy),.rxd(rxd),
 .rx_data(rx_data),.rx_valid(rx_valid),.rx_ready(rx_ready),.rx_busy(rx_busy),
 .overrun_error(overrun_error),.frame_error(frame_error),.prescale(16'(PRESCALE)));
integer checks=0,cycles=0,rx_count=0,frame_errors=0,overrun_errors=0;
integer tx_bad=0,rx_bad=0,loopback_bad=0,control_bad=0;
integer n,k,limit,base_count,base_errors;
reg [DATA_WIDTH-1:0] received[0:4095];
reg [31:0] rng=SEED;
reg pre_ready=0;

function [31:0] random_next;
input [31:0] x;
reg [31:0] t;
begin t=x^(x<<13);t=t^(t>>17);random_next=t^(t<<5);end
endfunction

function [DATA_WIDTH-1:0] word_value;
input integer i;
begin
 case(i)
 0:word_value=1;
 1:word_value=1<<(DATA_WIDTH-1);
 2:word_value=8'h96;
 3:word_value=0;
 4:word_value=MASK;
 default:begin rng=random_next(rng);word_value=rng;end
 endcase
end
endfunction

task tick;
begin
 clk=0;#4;
 pre_ready=tx_ready;
 if(!rst && rx_valid && rx_ready) begin
  if(rx_count>=4096)$fatal(1,"HARNESS receive queue overflow");
  received[rx_count]=rx_data;rx_count=rx_count+1;
 end
 clk=1;#1;cycles=cycles+1;
 if(^ {tx_ready,txd,tx_busy,rx_valid,rx_busy,frame_error,overrun_error}===1'bx)
  $fatal(1,"UNKNOWN external UART control");
 checks=checks+1;
 if(rst) begin
  if(txd!==1 || tx_busy!==0 || rx_valid!==0 || rx_busy!==0)
   $fatal(1,"RESET UART outputs did not return idle");
  checks=checks+1;
 end
 if(!rst) begin
  if(frame_error)frame_errors=frame_errors+1;
  if(overrun_error)overrun_errors=overrun_errors+1;
 end
 clk=0;#5;
end
endtask

task reset_design;
begin
 tx_valid=0;peer_line=1;loopback=0;rx_ready=1;
 rst=1;tick();tick();rst=0;repeat(BAUD*2)tick();
end
endtask

task wait_tx_ready;
integer wait_cycles;
begin
 wait_cycles=0;
 while((tx_ready!==1 || tx_busy!==0) && wait_cycles<BAUD*(DATA_WIDTH+5))begin tick();wait_cycles=wait_cycles+1;end
 if(tx_ready!==1 || tx_busy!==0)$fatal(1,"TX_PROGRESS no input acceptance capacity");
 checks=checks+1;
end
endtask

task transmit_word;
input [DATA_WIDTH-1:0] value;
input integer independent;
integer age,bit_index,bit_errors;
reg expected;
reg [DATA_WIDTH-1:0] observed;
begin
 wait_tx_ready();tx_data=value;tx_valid=1;tick();
 if(!pre_ready)$fatal(1,"HARNESS offer was not accepted");
 tx_valid=0;checks=checks+1;
 if(txd!==0)$fatal(1,"TX_START missing start after accepted byte");
 observed=0;bit_errors=0;
 for(age=0;age<(DATA_WIDTH+2)*BAUD;age=age+1)begin
  if(age>0)tick();
  bit_index=age/BAUD;
  expected=bit_index==0 ? 0 : bit_index>DATA_WIDTH ? 1 : (value>>(bit_index-1))&1;
  if(independent && txd!==expected)bit_errors=bit_errors+1;
  if(independent)checks=checks+1;
  for(bit_index=0;bit_index<DATA_WIDTH;bit_index=bit_index+1)
   if(age==(bit_index+1)*BAUD+BAUD/2)observed[bit_index]=txd;
 end
 if(independent)begin
  $display("UART_TX_FRAME offered=%h observed_lsb=%h bit_errors=%0d",value,observed,bit_errors);
  if(bit_errors)tx_bad=tx_bad+1;
 end
 wait_tx_ready();repeat(BAUD*2)tick();
end
endtask

task drive_serial;
input [DATA_WIDTH-1:0] value;
input integer bad_stop;
integer bit_index;
begin
 peer_line=0;repeat(BAUD)tick();
 for(bit_index=0;bit_index<DATA_WIDTH;bit_index=bit_index+1)begin
  peer_line=value[bit_index];repeat(BAUD)tick();
 end
 peer_line=!bad_stop;repeat(BAUD)tick();
 peer_line=1;repeat(BAUD*2)tick();
end
endtask

task receive_word;
input [DATA_WIDTH-1:0] value;
integer prior_count;
begin
 prior_count=rx_count;rx_ready=1;drive_serial(value,0);
 if(rx_count!=prior_count+1)begin
  $display("UART_RX_COUNT expected=1 actual=%0d",rx_count-prior_count);rx_bad=rx_bad+1;
 end else begin
  $display("UART_RX_FRAME sent_lsb=%h decoded=%h",value,received[prior_count]);
  if(received[prior_count]!==value)rx_bad=rx_bad+1;
 end
 checks=checks+1;
 if(frame_error || overrun_error)begin control_bad=control_bad+1;end
end
endtask

task loopback_word;
input [DATA_WIDTH-1:0] value;
integer prior_count;
begin
 prior_count=rx_count;loopback=1;rx_ready=1;transmit_word(value,0);
 if(rx_count!=prior_count+1 || received[prior_count]!==value)loopback_bad=loopback_bad+1;
 checks=checks+1;loopback=0;peer_line=1;repeat(BAUD)tick();
end
endtask

task stress_checks;
reg [DATA_WIDTH-1:0] held;
integer prior_count,error_before,age;
begin
 reset_design();
 // Pending output is stable while the downstream consumer pauses; no second
 // serial frame arrives during this particular stability check.
 rx_ready=0;prior_count=rx_count;drive_serial(1,0);held=rx_data;
 if(!rx_valid || held!==1)rx_bad=rx_bad+1;checks=checks+1;
 repeat(BAUD*3)begin
  tick();if(rx_valid!==1 || rx_data!==held)$fatal(1,"RX_STABILITY pending output changed");checks=checks+1;
 end
 rx_ready=1;tick();
 if(rx_count!=prior_count+1 || received[prior_count]!==1)rx_bad=rx_bad+1;checks=checks+1;
 // Serial RX cannot backpressure its peer. A second completed frame while
 // output is pending reports overrun and replaces the one-word output buffer.
 rx_ready=0;drive_serial(1,0);error_before=overrun_errors;
 drive_serial(1<<(DATA_WIDTH-1),0);
 if(overrun_errors!=error_before+1 || !rx_valid || rx_data!==(1<<(DATA_WIDTH-1)))
  control_bad=control_bad+1;
 checks=checks+1;rx_ready=1;tick();
 // Invalid stop must raise framing error and must not publish a byte.
 reset_design();prior_count=rx_count;error_before=frame_errors;drive_serial(8'h35,1);
 if(frame_errors<=error_before || rx_count!=prior_count)control_bad=control_bad+1;checks=checks+1;
 // Asynchronous reset interrupts an in-flight transmitter and receiver.
 reset_design();wait_tx_ready();tx_data=8'h61;tx_valid=1;tick();tx_valid=0;
 peer_line=0;repeat(BAUD*2)tick();rst=1;#1;
 if(txd!==1 || tx_busy!==0 || rx_valid!==0)control_bad=control_bad+1;checks=checks+1;
 tick();rst=0;peer_line=1;repeat(BAUD*3)tick();
 transmit_word(1,1);receive_word(1<<(DATA_WIDTH-1));
end
endtask

initial begin
 if(DATA_WIDTH<5 || DATA_WIDTH>8 || PRESCALE<1 || PRESCALE>8 || WORDS<1 || WORDS>64)
  $fatal(1,"HARNESS unsupported UART profile");
 reset_design();
 for(n=0;n<3;n=n+1)loopback_word(word_value(n));
 $display("UART_LOOPBACK_RESULT frames=3 failures=%0d",loopback_bad);
 if(!LOOPBACK_ONLY)begin
  for(n=0;n<WORDS;n=n+1)transmit_word(word_value(n),1);
  for(n=0;n<WORDS;n=n+1)receive_word(word_value(n));
  if(STRESS)stress_checks();
 end
 $display("UART_SUMMARY tx_mismatches=%0d rx_mismatches=%0d loopback_mismatches=%0d control_mismatches=%0d checks=%0d",tx_bad,rx_bad,loopback_bad,control_bad,checks);
 if(tx_bad || rx_bad || loopback_bad || control_bad)
  $fatal(1,"UART_PEER_CONTRACT_FAILED independent LSB-first serial peer disagrees");
 `RTLREFINE_DONE(checks);
end
endmodule
'''

PROFILES = [
    ('public_peer', 'public', 8, 2, 3, 0x3741a9b3, 0),
    ('uart8_fast', 'audit', 8, 1, 48, 0x4a91326f, 0),
    ('uart5', 'audit', 5, 3, 32, 0x713b8c21, 0),
    ('uart6', 'audit', 6, 2, 40, 0x5871d2a3, 0),
    ('uart7', 'audit', 7, 4, 40, 0x6bc78153, 0),
    ('uart8_slow', 'audit', 8, 5, 48, 0x1d5ecb73, 0),
    ('framing_reset', 'audit', 8, 3, 12, 0x421a9b31, 1),
    ('flow_overrun', 'audit', 7, 2, 16, 0x7539d2c1, 1),
]


def files_for(revision, *, smoke=False):
    provenance = json.loads((CASE / 'provenance.json').read_text())
    files = {'rtl/uart_pair.v': WRAPPER.encode(), 'LICENSE.upstream': (CASE / 'UPSTREAM_LICENSE').read_bytes()}
    for name in ('uart_tx.v', 'uart_rx.v'):
        source_revision = 'fixed' if revision == 'fixed' or revision == ('tx_only' if name == 'uart_tx.v' else 'rx_only') else 'original'
        value = (CASE / source_revision / 'rtl' / name).read_bytes()
        assert sha256(value) == provenance['revision'][source_revision]['files'][name]['sha256']
        files['rtl/' + name] = value
    tests = []
    for name, phase, width, prescale, words, seed, stress in PROFILES[:1] if smoke else PROFILES:
        top = 'tb_' + name
        path = 'tests/' + ('public.sv' if phase == 'public' else 'audit.sv')
        files[path] = BENCH.replace('TOP', 'tb_public' if phase == 'public' else 'tb_audit').encode()
        tests.append({'id': 'loopback_smoke' if smoke else name, 'phase': phase,
                      'top': 'tb_public' if phase == 'public' else 'tb_audit', 'files': [path],
                      'parameters': {'DATA_WIDTH': width, 'PRESCALE': prescale, 'WORDS': words, 'SEED': seed,
                                     'LOOPBACK_ONLY': int(smoke), 'STRESS': stress}, 'minimum_checks': 1})
    config = {'schema_version': 1, 'name': 'External UART: loopback versus independent LSB-first peers',
              'dut_top': 'uart_pair', 'rtl_files': ['rtl/uart_tx.v', 'rtl/uart_rx.v', 'rtl/uart_pair.v'],
              'editable_files': ['rtl/uart_tx.v', 'rtl/uart_rx.v'], 'dut_parameters': {'DATA_WIDTH': 8},
              'contract': 'UART data bits must be serialized and decoded LSB first, framed by a low start and high stop bit; prescale*8 clocks per bit, 5-8 data bits, no parity. Both directions are checked against independently generated serial peer bits. A TX/RX closed loopback is insufficient: the original pair shares the wrong order and can agree with itself. Preserve byte handshakes, framing/overrun reporting, asynchronous reset, and pending RX output when its consumer pauses and no new frame arrives. Wrapper and tests are read-only. No corrected reference implementation is supplied.',
              'tests': tests}
    files['rtlrefine.json'] = (json.dumps(config, indent=2) + '\n').encode()
    files['PROVENANCE.json'] = (json.dumps({'revision': revision, 'upstream': provenance,
        'stateless_readonly_adapter': True, 'scope': 'Explicit LSB-first peer contract; not new discovery, unbounded proof or unseen repair accuracy.'}, indent=2) + '\n').encode()
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['qualify', 'repair'])
    parser.add_argument('--output', required=True)
    parser.add_argument('--qualification')
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    if args.action == 'qualify':
        rows = []
        for name, revision, smoke in [('original_loopback', 'original', True), ('original_peer', 'original', False),
                                       ('maintainer_peer', 'fixed', False), ('tx_only_control', 'tx_only', False), ('rx_only_control', 'rx_only', False)]:
            project = load_project(files_for(revision, smoke=smoke))
            (out / (name + '.zip')).write_bytes(archive_project(project))
            result = run_project(project, output=out / name)
            tests = result.get('final_check', result['baseline'])['tests']
            row = {'case': name, 'accepted': result['accepted'], 'status': result['status'], 'api_requests': result['api_requests'],
                   'tests': [{k: t.get(k) for k in ['id', 'status', 'checks', 'log_tail']} for t in tests]}
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != 'tests'}), flush=True)
        good = [r['accepted'] for r in rows] == [True, False, True, False, False]
        seal = {'generator_sha256': sha256(Path(__file__).read_bytes()),
                'input_hashes': {p: sha256(v) for p, v in files_for('original').items()}}
        write_json(out / 'qualification.json', {'status': 'PASS' if good else 'QUALIFICATION_FAILED', 'cases': rows, 'seal': seal, 'new_model_calls': 0})
        if not good:
            raise SystemExit(1)
    else:
        if not args.qualification:
            raise ValueError('Provide a successful prospectively sealed qualification')
        q = json.loads(Path(args.qualification).read_text())
        assert q['status'] == 'PASS'
        assert q['seal']['generator_sha256'] == sha256(Path(__file__).read_bytes())
        assert q['seal']['input_hashes'] == {p: sha256(v) for p, v in files_for('original').items()}
        result = run_project(load_project(files_for('original')), repair=True, output=out / 'run', on_event=lambda e: print(e['message'], flush=True))
        write_json(out / 'summary.json', {k: result.get(k) for k in ['status', 'accepted', 'api_requests', 'wall_seconds', 'ci_status']})
        print(json.dumps({k: result.get(k) for k in ['status', 'accepted', 'api_requests', 'wall_seconds', 'ci_status']}, indent=2))


if __name__ == '__main__':
    main()
