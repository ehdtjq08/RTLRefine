"""The uploaded oracle may simulate and use data files, but not spawn programs."""
from .policy import PURE,tokens

BENCH_SYSTEM=PURE|{'$display','$write','$strobe','$monitor','$monitoron','$monitoroff','$finish','$stop','$warning','$info',
    '$dumpfile','$dumpvars','$dumpon','$dumpoff','$dumpall','$dumplimit','$dumpflush',
    '$random','$urandom','$urandom_range','$time','$stime','$realtime','$timeformat',
    '$itor','$rtoi','$bitstoreal','$realtobits','$shortrealtobits','$bitstoshortreal',
    '$fopen','$fclose','$fscanf','$fread','$fwrite','$fdisplay','$fstrobe','$fmonitor','$fgets','$fgetc','$ungetc',
    '$feof','$fseek','$ftell','$rewind','$fflush','$sscanf','$sformat','$sformatf','$psprintf',
    '$readmemh','$readmemb','$writememh','$writememb','$test$plusargs','$value$plusargs'}


def validate_test(source):
    ts=tokens(source)
    for i,(word,_,_,kind) in enumerate(ts):
        if kind in ('string','escaped','number'):continue
        if word.startswith('$') and word not in BENCH_SYSTEM:raise ValueError('Unsupported testbench host/process task: '+word)
        if word=='import' and i+1<len(ts) and ts[i+1][3]=='string':raise ValueError('DPI/foreign testbench code is not supported')
