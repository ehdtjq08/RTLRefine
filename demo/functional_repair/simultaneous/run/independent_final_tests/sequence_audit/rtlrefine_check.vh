`ifndef RTLREFINE_CHECK_VH
`define RTLREFINE_CHECK_VH
`define RTLREFINE_DONE(CHECKS) begin $display("RTLREFINE_PASS nonce=aabb5100c4a32001144bdd055d9b949b checks=%0d", (CHECKS)); $finish; end
`endif
