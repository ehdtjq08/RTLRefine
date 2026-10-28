module __rtlrefine_replay_tb;
reg clk=0,rst=0,s_valid=0,m_ready=0;
reg [3:0] s_data=0;
wire s_ready,m_valid;wire [3:0] m_data;
packet_queue #(.WIDTH(4),.DEPTH(4)) dut(.clk(clk),.rst(rst),.s_valid(s_valid),.s_ready(s_ready),.s_data(s_data),.m_valid(m_valid),.m_ready(m_ready),.m_data(m_data));
task step;
input integer cycle,reset_value,valid_value,data_value,ready_value;
begin
    clk=0;rst=reset_value;s_valid=valid_value;s_data=data_value;m_ready=ready_value;
    #2;$display("FIFO_OBS %0d %b %b %b",cycle,s_ready,m_valid,m_data);
    clk=1;#1;clk=0;#1;
end
endtask
initial begin
step(0,1,0,0,0);
step(1,0,1,2,0);
step(2,0,1,0,1);
step(3,0,1,10,1);
step(4,0,1,6,1);
step(5,0,0,0,0);
$finish;end
endmodule
