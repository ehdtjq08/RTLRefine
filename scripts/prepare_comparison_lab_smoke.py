"""Author three tiny integration cases, never used as AI performance evidence."""
import argparse
from pathlib import Path
import random

from rtl_agent.common import write_json

SOURCE='''// RTLRefine integration fixture, MIT, 2026-10-23. Not an AI achievement.
module smoke_counter(input wire clk, input wire rst, input wire en, output wire [7:0] count);
reg [7:0] count_reg=0, count_next;
assign count=count_reg;
always @* begin
    count_next = DEFAULT;
    if (en) count_next = count_reg + STEP;
end
always @(posedge clk) begin
    count_reg <= count_next;
    if (rst) begin
        count_reg <= 0;
    end
end
endmodule
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=False);cases=[]
    for name,default,step,kind in (('retention_fault',"8'd0","8'd1",'synthetic_injected'),
                                  ('grammar_miss','count_reg',"8'd2",'synthetic_injected'),
                                  ('normal','count_reg',"8'd1",'normal_control')):
        folder=root/name;folder.mkdir();(folder/'input.v').write_text(SOURCE.replace('DEFAULT',default).replace('STEP',step))
        traces=[]
        for i,(cycles,seed) in enumerate(((32,17),(64,29),(96,41))):
            trace=folder/f'trace_{i}';trace.mkdir();rng=random.Random(seed);counter=0;stim=[];expected=[]
            for cycle in range(cycles):
                reset=cycle<2 or cycle==cycles//2;enable=rng.randrange(2)
                stim.append(f'{enable:x} {int(reset):x}\n');expected.append(f'{counter:x}\n')
                counter=0 if reset else (counter+enable)&255
            (trace/'stimulus.hex').write_text(''.join(stim));(trace/'expected.hex').write_text(''.join(expected))
            traces.append({'stimulus':f'{name}/trace_{i}/stimulus.hex','expected':f'{name}/trace_{i}/expected.hex',
                'cycles':cycles,'inputs':['en','rst'],'outputs':['count'],'label':'discovery' if i==0 else f'audit_{i}'})
        cases.append({'id':name,'project':'local/comparison-lab-integration-fixture','top':'smoke_counter','clock':'clk',
            'source':f'{name}/input.v','kind':kind,'traces':traces})
    write_json(root/'cases.json',{'cohort':'native_system_validation_only','exposure':'previously_examined',
        'oracle_scope':'Independent Python increment/reset recurrence, before-edge outputs; integration fixture only',
        'validation_fixture':True,'cases':cases})
    print(root/'cases.json')


if __name__=='__main__':main()
