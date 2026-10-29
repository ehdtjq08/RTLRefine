FROM mambaorg/micromamba:2.9.0@sha256:4f29a2b62a6e65ffa3dfbccb62d8a90514e95954aae52a90afaa8e7dae347bbf

USER root
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap util-linux ca-certificates && rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install --yes -n base -f /tmp/environment.yml && micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
WORKDIR /app
COPY --chown=$MAMBA_USER:$MAMBA_USER requirements-ui.lock /app/requirements-ui.lock
RUN python -m pip install --no-cache-dir -r requirements-ui.lock
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts/install_verilator_pinned.py /app/scripts/install_verilator_pinned.py
USER root
RUN apt-get update && apt-get install -y --no-install-recommends g++ make && rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER
RUN python /app/scripts/install_verilator_pinned.py
COPY --chown=$MAMBA_USER:$MAMBA_USER rtl_app.py workspace_app.py workspace_service.py case_gallery_app.py comparison_app.py /app/
COPY --chown=$MAMBA_USER:$MAMBA_USER mutation_app.py /app/mutation_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER uart_app.py /app/uart_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER known_bugs_v2_app.py /app/known_bugs_v2_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER repair_search_app.py /app/repair_search_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER evidence_ranking_app.py /app/evidence_ranking_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER repair_studio_app.py /app/repair_studio_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER project_app.py /app/project_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER property_app.py /app/property_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER external_validation_app.py /app/external_validation_app.py
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts/run_known_bug_comparison_v2.py /app/scripts/run_known_bug_comparison_v2.py
COPY --chown=$MAMBA_USER:$MAMBA_USER rtl_agent /app/rtl_agent
COPY --chown=$MAMBA_USER:$MAMBA_USER LICENSE /app/LICENSE
COPY --chown=$MAMBA_USER:$MAMBA_USER configs /app/configs
COPY --chown=$MAMBA_USER:$MAMBA_USER third_party/verilog_axis_reset /app/third_party/verilog_axis_reset
COPY --chown=$MAMBA_USER:$MAMBA_USER third_party/verilog_axis_adapter_keep /app/third_party/verilog_axis_adapter_keep
COPY --chown=$MAMBA_USER:$MAMBA_USER third_party/verilog_axis_frame /app/third_party/verilog_axis_frame
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/fifo_reset /app/demo/fifo_reset
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/adapter_keep /app/demo/adapter_keep
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/sequential_cases /app/demo/sequential_cases
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/sequential_comparison /app/demo/sequential_comparison
COPY --chown=$MAMBA_USER:$MAMBA_USER mutation_cases /app/mutation_cases
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/mutation_challenge /app/demo/mutation_challenge
COPY --chown=$MAMBA_USER:$MAMBA_USER external_cases /app/external_cases
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/external_uart /app/demo/external_uart
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/known_bug_comparison_v2 /app/demo/known_bug_comparison_v2
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/repair_search /app/demo/repair_search
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/evidence_ranking /app/demo/evidence_ranking
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/repair_studio /app/demo/repair_studio
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/property_repair /app/demo/property_repair
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/functional_repair /app/demo/functional_repair
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/external_rtl_validation /app/demo/external_rtl_validation
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/general_project_ci /app/demo/general_project_ci
COPY --chown=$MAMBA_USER:$MAMBA_USER demo/uart_peer /app/demo/uart_peer
COPY --chown=$MAMBA_USER:$MAMBA_USER assets /app/assets
COPY --chown=$MAMBA_USER:$MAMBA_USER .streamlit/config.toml /app/.streamlit/config.toml
COPY --chown=$MAMBA_USER:$MAMBA_USER docs/PROPERTY_REPAIR_PROTOCOL.md /app/docs/PROPERTY_REPAIR_PROTOCOL.md
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts/check_general_project_ci.py /app/scripts/check_general_project_ci.py
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts/validate_external_uart_bitorder.py /app/scripts/validate_external_uart_bitorder.py
RUN mkdir -p /app/results /app/.state
ENV RTLREFINE_ENABLE_LIVE_MODEL=0
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "rtl_app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.maxUploadSize", "10", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
