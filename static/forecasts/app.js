(function () {
  const { createApp, nextTick } = Vue;
  if (window.Chart && window.ChartZoom) {
    Chart.register(window.ChartZoom);
  }

  createApp({
    data() {
      return {
        sites: [],
        runs: [],
        schedules: [],
        selectedRun: null,
        isLaunching: false,
        isSavingSchedule: false,
        pollingHandle: null,
        pollingFastMs: 3000,
        pollingIdleMs: 30000,
        runForm: {
          site: "",
          model: "simple_copy",
          n_splits: 4,
          gap: 0,
          test_size: 96,
        },
        scheduleForm: {
          schedule_id: null,
          site: "",
          model: "simple_copy",
          n_splits: 4,
          gap: 0,
          test_size: 96,
          active: true,
        },
        filters: {
          site: "",
          status: "",
        },
        charts: {
          combined: null,
          residual: null,
        },
      };
    },
    computed: {
      filteredRuns() {
        return this.runs.filter((run) => {
          const siteOk = !this.filters.site || run.site === this.filters.site;
          const statusOk = !this.filters.status || run.status === this.filters.status;
          return siteOk && statusOk;
        });
      },
      scoringModelColumns() {
        if (!this.selectedRun || !Array.isArray(this.selectedRun.scoring_details)) {
          return [];
        }
        const names = new Set();
        this.selectedRun.scoring_details.forEach((row) => {
          if (row && row.model_rmse) {
            Object.keys(row.model_rmse).forEach((name) => names.add(name));
          }
        });
        return Array.from(names).sort();
      },
      scoringAverages() {
        if (!this.selectedRun || !Array.isArray(this.selectedRun.scoring_details)) {
          return { testStd: null, modelRmse: {} };
        }
        const rows = this.selectedRun.scoring_details;
        const finite = (v) => {
          const n = Number(v);
          return Number.isFinite(n) ? n : null;
        };

        const testStdVals = rows
          .map((r) => finite(r.test_std))
          .filter((v) => v !== null);
        const avg = (vals) =>
          vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;

        const modelRmse = {};
        this.scoringModelColumns.forEach((modelName) => {
          const vals = rows
            .map((r) => (r.model_rmse ? finite(r.model_rmse[modelName]) : null))
            .filter((v) => v !== null);
          modelRmse[modelName] = avg(vals);
        });

        return {
          testStd: avg(testStdVals),
          modelRmse,
        };
      },
      isEditingSchedule() {
        return Boolean(this.scheduleForm.schedule_id);
      },
    },
    methods: {
      resetScheduleForm() {
        this.scheduleForm = {
          schedule_id: null,
          site: this.sites[0] || "",
          model: "simple_copy",
          n_splits: 4,
          gap: 0,
          test_size: 96,
          active: true,
        };
      },
      editSchedule(schedule) {
        this.scheduleForm = {
          schedule_id: schedule.schedule_id,
          site: schedule.site,
          model: schedule.model,
          n_splits: schedule.n_splits,
          gap: schedule.gap,
          test_size: schedule.test_size,
          active: schedule.active,
        };
      },
      async loadSites() {
        const response = await fetch("/forecasts/sites");
        const payload = await response.json();
        this.sites = payload.sites || [];
        if (!this.runForm.site && this.sites.length > 0) {
          this.runForm.site = this.sites[0];
        }
        if (!this.scheduleForm.site && this.sites.length > 0) {
          this.scheduleForm.site = this.sites[0];
        }
      },
      async refreshRuns() {
        const response = await fetch("/forecasts/runs");
        this.runs = await response.json();
      },
      async refreshSchedules() {
        const response = await fetch("/forecasts/schedules");
        this.schedules = await response.json();
      },
      async toggleScheduleActive(schedule, nextActive) {
        try {
          const response = await fetch(`/forecasts/schedules/${schedule.schedule_id}/active`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ active: nextActive }),
          });
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.detail || "Unable to update schedule state.");
          }
          await this.refreshSchedules();
        } catch (err) {
          alert(err.message);
        }
      },
      async deleteSchedule(schedule) {
        try {
          const response = await fetch(`/forecasts/schedules/${schedule.schedule_id}`, {
            method: "DELETE",
          });
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.detail || "Unable to delete schedule.");
          }
          if (this.scheduleForm.schedule_id === schedule.schedule_id) {
            this.resetScheduleForm();
          }
          await this.refreshSchedules();
        } catch (err) {
          alert(err.message);
        }
      },
      async launchRun() {
        this.isLaunching = true;
        try {
          const response = await fetch("/forecasts/runs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(this.runForm),
          });
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.detail || "Run creation failed.");
          }
          await this.refreshRuns();
          await this.openRun(payload.run_id);
        } catch (err) {
          alert(err.message);
        } finally {
          this.isLaunching = false;
        }
      },
      async saveSchedule() {
        this.isSavingSchedule = true;
        try {
          const isEditing = Boolean(this.scheduleForm.schedule_id);
          const response = await fetch(
            isEditing
              ? `/forecasts/schedules/${this.scheduleForm.schedule_id}`
              : "/forecasts/schedules",
            {
              method: isEditing ? "PATCH" : "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                site: this.scheduleForm.site,
                model: this.scheduleForm.model,
                n_splits: this.scheduleForm.n_splits,
                gap: this.scheduleForm.gap,
                test_size: this.scheduleForm.test_size,
                active: this.scheduleForm.active,
              }),
            },
          );
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.detail || "Schedule save failed.");
          }
          await this.refreshSchedules();
          this.resetScheduleForm();
        } catch (err) {
          alert(err.message);
        } finally {
          this.isSavingSchedule = false;
        }
      },
      async openRun(runId) {
        const response = await fetch(`/forecasts/runs/${runId}`);
        const payload = await response.json();
        if (!response.ok) {
          if (this.selectedRun && this.selectedRun.run_id === runId) {
            this.selectedRun.status = "failed";
            this.selectedRun.error = payload.detail || "Unable to load run details.";
          }
          return false;
        }
        this.selectedRun = payload;
        await nextTick();
        this.renderCharts();
        return true;
      },
      renderCharts() {
        if (!this.selectedRun || this.selectedRun.status !== "done") {
          this.destroyCharts();
          return;
        }
        this.destroyCharts();
        const inRows = this.selectedRun.in_sample_chart || [];
        const outRows = this.selectedRun.out_of_sample_chart || [];
        const resRows = this.selectedRun.residual_chart || [];
        if (inRows.length === 0 && outRows.length === 0) {
          return;
        }

        const combinedCtx = document.getElementById("combinedChart");
        const resCtx = document.getElementById("residualChart");
        if (!combinedCtx || !resCtx) {
          return;
        }

        const toNum = (v) => {
          const n = Number(v);
          return Number.isFinite(n) ? n : null;
        };
        const labels = [...inRows.map((r) => r.timestamp), ...outRows.map((r) => r.timestamp)];
        const actualCombined = [
          ...inRows.map((r) => toNum(r.actual)),
          ...outRows.map(() => null),
        ];
        const predictedCombined = [
          ...inRows.map((r) => toNum(r.predicted)),
          ...outRows.map((r) => toNum(r.predicted)),
        ];

        this.charts.combined = new Chart(combinedCtx, {
          type: "line",
          data: {
            labels,
            datasets: [
              {
                label: "Actual",
                data: actualCombined,
                borderColor: "#2ca02c",
                pointRadius: 1.2,
                pointHoverRadius: 5,
                pointHitRadius: 12,
                spanGaps: false,
              },
              {
                label: "Predicted / Forecast",
                data: predictedCombined,
                borderColor: "#244f9e",
                pointRadius: 1.2,
                pointHoverRadius: 5,
                pointHitRadius: 12,
                spanGaps: false,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
              mode: "index",
              intersect: false,
            },
            scales: {
              x: {
                min: 0,
                max: Math.max(0, labels.length - 1),
              },
            },
            plugins: {
              tooltip: {
                mode: "index",
                intersect: false,
              },
              zoom: {
                limits: {
                  x: { min: 0, max: Math.max(0, labels.length - 1) },
                },
                zoom: {
                  drag: {
                    enabled: true,
                    backgroundColor: "rgba(36,79,158,0.18)",
                    borderColor: "rgba(36,79,158,0.65)",
                    borderWidth: 1,
                  },
                  mode: "x",
                },
                pan: {
                  enabled: true,
                  mode: "x",
                },
              },
            },
          },
        });
        this.charts.residual = new Chart(resCtx, {
          type: "bar",
          data: {
            labels: resRows.map((r) => r.timestamp),
            datasets: [{ label: "Residual", data: resRows.map((r) => toNum(r.residual)), backgroundColor: "#d9603b" }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
              mode: "index",
              intersect: false,
            },
            plugins: {
              tooltip: {
                mode: "index",
                intersect: false,
              },
            },
          },
        });
      },
      destroyCharts() {
        Object.keys(this.charts).forEach((key) => {
          if (this.charts[key]) {
            this.charts[key].destroy();
            this.charts[key] = null;
          }
        });
      },
      resetZoom() {
        if (this.charts.combined && typeof this.charts.combined.resetZoom === "function") {
          this.charts.combined.resetZoom();
        }
        if (this.charts.residual && typeof this.charts.residual.resetZoom === "function") {
          this.charts.residual.resetZoom();
        }
      },
      formatTs(value) {
        if (!value) {
          return "-";
        }
        return new Date(value).toLocaleString("fr-FR", { timeZone: "Europe/Paris" });
      },
      formatNum(value) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) {
          return "-";
        }
        return Number(value).toFixed(4);
      },
      startPolling() {
        this.stopPolling();
        const loop = async () => {
          let nextDelay = this.pollingIdleMs;
          try {
            const hasActiveRun = this.runs.some((run) => ["queued", "running"].includes(run.status));
            const selectedActive =
              this.selectedRun && ["queued", "running"].includes(this.selectedRun.status);

            // Always refresh at least once per cycle, but use a slow cadence when idle.
            await this.refreshRuns();

            if (selectedActive) {
              const ok = await this.openRun(this.selectedRun.run_id);
              if (!ok) {
                nextDelay = this.pollingIdleMs;
              } else {
                nextDelay = this.pollingFastMs;
              }
            } else if (hasActiveRun) {
              nextDelay = this.pollingFastMs;
            } else {
              nextDelay = this.pollingIdleMs;
            }
          } catch (_err) {
            nextDelay = 10000;
          }
          if (this.pollingHandle !== null) {
            this.pollingHandle = setTimeout(loop, nextDelay);
          }
        };
        this.pollingHandle = setTimeout(loop, 0);
      },
      stopPolling() {
        if (this.pollingHandle !== null) {
          clearTimeout(this.pollingHandle);
          this.pollingHandle = null;
        }
      },
    },
    async mounted() {
      await this.loadSites();
      await this.refreshRuns();
      await this.refreshSchedules();
      this.startPolling();
    },
    beforeUnmount() {
      this.stopPolling();
      this.destroyCharts();
    },
  }).mount("#app");
})();
