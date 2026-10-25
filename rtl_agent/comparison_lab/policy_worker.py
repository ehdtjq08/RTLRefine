"""Executed inside the isolated policy worker; standard library only."""
import importlib.util
import json
import sys


def main():
    payload=json.load(sys.stdin)
    spec=importlib.util.spec_from_file_location('candidate_policy','/work/policy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    order=module.rank(payload['public'],payload['views'],payload['seed'])
    json.dump({'order':order},sys.stdout)


if __name__=='__main__':main()
