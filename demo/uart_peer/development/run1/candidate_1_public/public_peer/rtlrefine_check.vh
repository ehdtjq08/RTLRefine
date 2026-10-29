`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=bb5b32f091a72c9f50ca2d44bfb14a9f checks=%0d", (CHECKS)); $finish; end
`endif
