`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=f1b4f4b42ebee365d95e2394083ad47a checks=%0d", (CHECKS)); $finish; end
`endif
