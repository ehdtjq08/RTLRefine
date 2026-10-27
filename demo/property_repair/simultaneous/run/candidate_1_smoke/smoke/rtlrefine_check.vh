`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=12d1ce953f48237ab2510fa0814fd28a checks=%0d", (CHECKS)); $finish; end
`endif
