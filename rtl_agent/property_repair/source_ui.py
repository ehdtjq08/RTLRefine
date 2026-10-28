"""Optional designer edits retain the same interface and verification gates."""
import streamlit as st

from ..common import sha256
from ..project_repair.project import load_project
from ..project_repair.policy import validate_patch


def source_editor(project):
    key='fifo_source_'+project.identity[:16]
    with st.expander('Original design source'):
        editable=st.toggle('Edit permitted DUT logic before checking',value=False,key=key+'enabled')
        if not editable:
            for path,text in project.editable.items():st.caption(path);st.code(text,language='verilog',line_numbers=True)
            return project
        st.caption('Ports, parameters, license headers and clock/reset event forms stay fixed. Any source edit needs a fresh check; no model request is made by editing.')
        names=list(project.editable)
        path=st.selectbox('Editable DUT file',names,key=key+'file')
        def field(name):return key+sha256(name.encode())[:12]
        st.text_area('DUT source',project.editable[path],height=340,max_chars=240000,key=field(path))
        changes={name:st.session_state[field(name)] for name in names if field(name) in st.session_state and st.session_state[field(name)]!=project.editable[name]}
        if changes:
            validate_patch(project,changes)
            return load_project({**project.files,**{name:text.encode() for name,text in changes.items()}},project.config)
    return project
