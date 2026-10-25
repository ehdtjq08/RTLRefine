`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;
reg rst=1,s_valid=0,s_last=0,s_user=0,m_ready=0;
reg [7:0] s_data=0;
wire s_ready,m_valid,m_last,m_user;wire [7:0] m_data;
stream_buffer #(.ADDR_WIDTH(1),.DATA_WIDTH(8)) dut(.*);
reg rst_vec[0:15];
reg valid_vec[0:15];
reg [7:0] data_vec[0:15];
reg last_vec[0:15];
reg user_vec[0:15];
reg ready_vec[0:15];
reg consumed=0;
integer cycle=-1,observations,i;
always @(posedge clk) begin
 consumed=(!rst && s_valid && s_ready);
 if(cycle>=0) $fdisplay(observations,"%0d,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b,%b",cycle,rst,s_valid,s_ready,s_data,s_last,s_user,m_valid,m_ready,m_data,m_last,m_user);
end
initial begin
 observations=$fopen("observed.csv","w");$dumpfile("trace.vcd");$dumpvars(0,tb);
rst_vec[0]=1;valid_vec[0]=0;data_vec[0]=8'd0;last_vec[0]=0;user_vec[0]=0;ready_vec[0]=0;
rst_vec[1]=0;valid_vec[1]=1;data_vec[1]=8'd159;last_vec[1]=1;user_vec[1]=0;ready_vec[1]=0;
rst_vec[2]=1;valid_vec[2]=1;data_vec[2]=8'd63;last_vec[2]=1;user_vec[2]=0;ready_vec[2]=1;
rst_vec[3]=0;valid_vec[3]=1;data_vec[3]=8'd118;last_vec[3]=1;user_vec[3]=1;ready_vec[3]=0;
rst_vec[4]=0;valid_vec[4]=1;data_vec[4]=8'd91;last_vec[4]=0;user_vec[4]=1;ready_vec[4]=0;
rst_vec[5]=0;valid_vec[5]=0;data_vec[5]=8'd184;last_vec[5]=0;user_vec[5]=0;ready_vec[5]=0;
rst_vec[6]=0;valid_vec[6]=0;data_vec[6]=8'd9;last_vec[6]=0;user_vec[6]=1;ready_vec[6]=1;
rst_vec[7]=0;valid_vec[7]=1;data_vec[7]=8'd97;last_vec[7]=1;user_vec[7]=1;ready_vec[7]=1;
rst_vec[8]=0;valid_vec[8]=0;data_vec[8]=8'd139;last_vec[8]=1;user_vec[8]=0;ready_vec[8]=0;
rst_vec[9]=0;valid_vec[9]=1;data_vec[9]=8'd11;last_vec[9]=0;user_vec[9]=1;ready_vec[9]=0;
rst_vec[10]=0;valid_vec[10]=1;data_vec[10]=8'd3;last_vec[10]=0;user_vec[10]=0;ready_vec[10]=1;
rst_vec[11]=0;valid_vec[11]=1;data_vec[11]=8'd67;last_vec[11]=0;user_vec[11]=1;ready_vec[11]=0;
rst_vec[12]=0;valid_vec[12]=1;data_vec[12]=8'd67;last_vec[12]=0;user_vec[12]=1;ready_vec[12]=0;
rst_vec[13]=0;valid_vec[13]=1;data_vec[13]=8'd67;last_vec[13]=0;user_vec[13]=1;ready_vec[13]=0;
rst_vec[14]=0;valid_vec[14]=1;data_vec[14]=8'd67;last_vec[14]=0;user_vec[14]=1;ready_vec[14]=1;
rst_vec[15]=0;valid_vec[15]=0;data_vec[15]=8'd44;last_vec[15]=0;user_vec[15]=0;ready_vec[15]=1;
 for(i=0;i<16;i=i+1) begin
  @(negedge clk);cycle=i;rst=rst_vec[i];m_ready=ready_vec[i];
  s_valid=valid_vec[i];s_data=data_vec[i];s_last=last_vec[i];s_user=user_vec[i];
  @(posedge clk);
 end
 @(negedge clk);$fclose(observations);$finish;
end
initial begin #100000;$fatal(1,"Timed out");end
endmodule
