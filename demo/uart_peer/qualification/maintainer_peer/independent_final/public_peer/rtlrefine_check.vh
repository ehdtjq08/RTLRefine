`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=03caea5583accf07843a458b03664cbc checks=%0d", (CHECKS)); $finish; end
`endif
