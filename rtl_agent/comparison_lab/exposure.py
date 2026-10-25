"""Local project-exposure audit, shared across renamed dataset bundles."""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path

from ..common import ROOT
from .collect import atomic_json
from .data import canonical_project

REGISTRY=ROOT/'.state/comparison_lab/project_exposure.json'


@contextmanager
def locked_registry():
    REGISTRY.parent.mkdir(parents=True,exist_ok=True)
    with REGISTRY.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        value=json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {'projects':{}}
        value['projects']={canonical_project(k):v for k,v in value['projects'].items()}
        try:
            yield value
            atomic_json(REGISTRY,value)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def reserve(projects,protocol_sha256,*,parent_study=None,state='reserved'):
    projects={canonical_project(p) for p in projects}
    with locked_registry() as registry:
        for group in projects:
            prior=registry['projects'].get(group)
            matches_study=prior and prior['state']=='registered' and prior['protocol_sha256']==parent_study
            if prior and not matches_study and (prior['state']=='opened' or prior['protocol_sha256']!=protocol_sha256):
                raise ValueError('Project already exposed or reserved for another final protocol: '+group)
        for group in projects:registry['projects'][group]={'state':state,'protocol_sha256':protocol_sha256}


def verify_reservation(projects,protocol_sha256):
    projects={canonical_project(p) for p in projects}
    with locked_registry() as registry:
        for group in projects:
            prior=registry['projects'].get(group)
            if not prior or prior['protocol_sha256']!=protocol_sha256:
                raise ValueError('Final project reservation does not match the registered protocol')


def opened(projects,protocol_sha256,mode):
    projects={canonical_project(p) for p in projects}
    with locked_registry() as registry:
        for group in projects:
            prior=registry['projects'].get(group)
            if mode=='confirmatory' and prior and prior['protocol_sha256']!=protocol_sha256:
                raise ValueError('Final project belongs to a different protocol')
        for group in projects:registry['projects'][group]={'state':'opened','protocol_sha256':protocol_sha256,'mode':mode}
