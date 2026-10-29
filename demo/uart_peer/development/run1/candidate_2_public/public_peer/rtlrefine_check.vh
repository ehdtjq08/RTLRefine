`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=32c052ba7189534a40f891790fc35b5f checks=%0d", (CHECKS)); $finish; end
`endif
