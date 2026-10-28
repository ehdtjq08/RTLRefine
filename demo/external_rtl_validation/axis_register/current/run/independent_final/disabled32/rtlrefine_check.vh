`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=04d01c56d38623fa86690ec3d362cfb9 checks=%0d", (CHECKS)); $finish; end
`endif
