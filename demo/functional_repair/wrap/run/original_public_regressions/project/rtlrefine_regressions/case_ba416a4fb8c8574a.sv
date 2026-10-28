// Generated from public input stimuli and an independent FIFO contract.
// No observed output from the failing DUT is used as an expected value.
module __rtlrefine_regression_case_ba416a4fb8c8574a;
reg clk=0,rst=0,s_valid=0,m_ready=0;
reg [3:0] s_data=0;
wire s_ready,m_valid;
wire [3:0] m_data;
integer checks=0;
packet_queue #(.DEPTH(4),.WIDTH(4)) dut(.clk(clk),.m_data(m_data),.m_ready(m_ready),.m_valid(m_valid),.rst(rst),.s_data(s_data),.s_ready(s_ready),.s_valid(s_valid));
task step;
input integer cycle,reset_value,valid_value,data_value,ready_value,expect_ready,expect_valid,expect_data,check_data,after_ready,after_valid,after_data,check_after;
begin
    clk=0;rst=reset_value;s_valid=valid_value;s_data=data_value;m_ready=ready_value;#2;
    if(s_ready !== expect_ready[0]) $fatal(1,"step=%0d ready actual=%b expected=%b",cycle,s_ready,expect_ready[0]);
    checks=checks+1;
    if(m_valid !== expect_valid[0]) $fatal(1,"step=%0d valid actual=%b expected=%b",cycle,m_valid,expect_valid[0]);
    checks=checks+1;
    if(check_data) begin
        if(m_data !== expect_data[3:0]) $fatal(1,"step=%0d payload actual=%h expected=%h",cycle,m_data,expect_data);
        checks=checks+1;
    end
    clk=1;#1;
    if(s_ready !== after_ready[0]) $fatal(1,"step=%0d post-edge ready actual=%b expected=%b",cycle,s_ready,after_ready[0]);
    checks=checks+1;
    if(m_valid !== after_valid[0]) $fatal(1,"step=%0d post-edge valid actual=%b expected=%b",cycle,m_valid,after_valid[0]);
    checks=checks+1;
    if(check_after) begin
        if(m_data !== after_data[3:0]) $fatal(1,"step=%0d post-edge payload actual=%h expected=%h",cycle,m_data,after_data);
        checks=checks+1;
    end
    clk=0;#1;
end
endtask
initial begin
step(1,1,0,0,0,0,0,0,0,0,0,0,0);
step(2,0,1,1,0,1,0,0,0,1,1,1,1);
step(3,0,1,2,0,1,1,1,1,1,1,1,1);
step(4,0,1,3,0,1,1,1,1,1,1,1,1);
step(5,0,1,4,0,1,1,1,1,0,1,1,1);
step(6,0,0,0,0,0,1,1,1,0,1,1,1);
step(7,0,0,0,0,0,1,1,1,0,1,1,1);
step(8,0,1,9,1,1,1,1,1,1,1,2,1);
step(9,0,1,10,1,1,1,2,1,1,1,3,1);
step(10,0,1,11,1,1,1,3,1,1,1,4,1);
step(11,0,1,12,1,1,1,4,1,1,1,9,1);
step(12,0,1,13,1,1,1,9,1,1,1,10,1);
step(13,0,1,14,1,1,1,10,1,1,1,11,1);
step(14,0,0,0,1,1,1,11,1,1,1,12,1);
step(15,0,0,0,1,1,1,12,1,1,1,13,1);
step(16,0,0,0,1,1,1,13,1,1,1,14,1);
step(17,0,0,0,1,1,1,14,1,1,0,0,0);
step(18,0,0,0,1,1,0,0,0,1,0,0,0);
step(19,0,1,3,0,1,0,0,0,1,1,3,1);
step(20,0,1,5,0,1,1,3,1,1,1,3,1);
step(21,1,1,15,1,0,0,0,0,0,0,0,0);
step(22,0,1,5,0,1,0,0,0,1,1,5,1);
step(23,0,1,6,0,1,1,5,1,1,1,5,1);
step(24,0,1,7,0,1,1,5,1,1,1,5,1);
step(25,0,1,8,0,1,1,5,1,0,1,5,1);
step(26,0,0,0,1,1,1,5,1,1,1,6,1);
step(27,0,0,0,1,1,1,6,1,1,1,7,1);
step(28,0,0,0,1,1,1,7,1,1,1,8,1);
step(29,0,0,0,1,1,1,8,1,1,0,0,0);
step(30,0,0,0,1,1,0,0,0,1,0,0,0);
$display("RTLREFINE_REGRESSION_PASS checks=%0d",checks);
$finish;end
endmodule
