# Portable FIFO regressions

From the extracted project root, run:

    python3 -I rtlrefine_regressions/run.py --report regression-report.json

Prerequisites: Linux, Python 3.10+, Icarus Verilog/vvp, bubblewrap and prlimit.
The RTLRefine Docker test build includes the native tools. No API key, model,
Streamlit or Yosys is needed. The runner never falls back to unisolated RTL.

Design source may change: every run compiles a fresh source snapshot and reports
its hashes. The contract, compile configuration, generated benches and runner
are fixed. Regenerate the bundle through RTLRefine if those settings change.
Only these finite regression stimuli are checked; rerun the full application
for the original benches and bounded properties. A zero exit means every
regression passed; exit 1 is a reproduced regression and exit 2 is a setup,
configuration or integrity error. Test expectations come from the contract,
never from the output of a failing implementation. The files in this folder
are tool-owned; keep your own notes elsewhere.

The generated runner and benches are distributed under this license:

MIT License

Copyright (c) 2026 RTLRefine contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

