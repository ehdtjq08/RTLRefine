#include "Vaxis_adapter.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
int main(int argc,char** argv) {
 Verilated::commandArgs(argc,argv);Verilated::randReset(0);
 Vaxis_adapter dut;
 bool capture=argc==2 && std::string(argv[1])=="capture";
 std::ifstream stim("stimulus.hex"),oracle("expected.hex");
 std::ofstream observed;if(capture) observed.open("observed.hex");
 if(!stim || (!capture && !oracle)) return 3;
 std::string iline,eline;uint64_t cycle=0,errors=0,comparisons=0;
 std::vector<std::string> history;
 while(std::getline(stim,iline)) {
  if(iline.empty()) continue;
  uint64_t input_values[7];
  std::istringstream in(iline);in>>std::hex;
  for(auto &v:input_values) if(!(in>>v)) return 4;
  dut.clk=0;
dut.input_axis_tdata=input_values[0];
dut.input_axis_tkeep=input_values[1];
dut.input_axis_tlast=input_values[2];
dut.input_axis_tuser=input_values[3];
dut.input_axis_tvalid=input_values[4];
dut.output_axis_tready=input_values[5];
dut.rst=input_values[6];
  dut.eval();
  uint64_t output_values[]={static_cast<uint64_t>(dut.input_axis_tready),static_cast<uint64_t>(dut.output_axis_tdata),static_cast<uint64_t>(dut.output_axis_tkeep),static_cast<uint64_t>(dut.output_axis_tlast),static_cast<uint64_t>(dut.output_axis_tuser),static_cast<uint64_t>(dut.output_axis_tvalid)};
  history.push_back(iline);if(history.size()>9) history.erase(history.begin());
  if(capture) { for(auto v:output_values) observed<<std::hex<<v<<" ";observed<<"\n"; }
  else {
   if(!std::getline(oracle,eline)) return 5;
   std::istringstream expected(eline);std::string token;
   for(size_t j=0;j<6;j++) {
    if(!(expected>>token)) return 6;
    if(token=="?") continue;
    comparisons++;
    uint64_t want=std::stoull(token,nullptr,16);
    if(want!=output_values[j]) {
     if(errors<10) {
      std::cout<<"MISMATCH "<<std::dec<<cycle<<" "<<j<<" "<<std::hex<<want<<" "<<output_values[j]<<"\n";
      std::cout<<"INPUT_WINDOW "<<std::dec<<(cycle+1-history.size());
      for(auto &h:history) std::cout<<" | "<<h;
      std::cout<<"\n";
     }
     errors++;
    }
   }
  }
  dut.clk=1;dut.eval();
  dut.clk=0;dut.eval();cycle++;
 }
 dut.final();
 std::cout<<"SUMMARY "<<std::dec<<cycle<<" "<<errors<<" "<<comparisons<<"\n";
 return 0;
}
