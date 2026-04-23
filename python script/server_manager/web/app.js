const { createApp, ref, computed, onMounted } = Vue;

createApp({
  setup() {
    const report = ref(null);
    const status = ref({});
    const files = ref({});
    const loading = ref(false);
    const error = ref("");
    const mainPanel = ref("cost");
    const activeTab = ref("instances");
    const search = ref("");
    const copiedIntel = ref(false);
    const appUrl = `${window.location.protocol}//${window.location.host}`;

    const safeArray = (value) => (Array.isArray(value) ? value : []);
    const safeNumber = (value) => (typeof value === "number" ? value : 0);

    const totals = computed(() => {
      return (
        report.value?.totals ?? {
          instances_monthly_eur: 0,
          volumes_monthly_eur: 0,
          flexible_ips_monthly_eur: 0,
          object_storage_monthly_eur: 0,
          grand_total_monthly_eur: 0,
        }
      );
    });

    const securityGroups = computed(() =>
      safeArray(report.value?.security_groups).slice().sort((left, right) => {
        return `${left.zone}-${left.name}`.localeCompare(`${right.zone}-${right.name}`);
      })
    );

    const warnings = computed(() => {
      const reportWarnings = safeArray(report.value?.warnings);
      const runtimeWarnings = [];
      if (!status.value?.boto3_installed) {
        runtimeWarnings.push(
          "boto3 is missing locally, so Object Storage buckets cannot be scanned yet."
        );
      }
      if (status.value?.config_error) {
        runtimeWarnings.push(status.value.config_error);
      }
      if (error.value) {
        runtimeWarnings.unshift(error.value);
      }
      return [...runtimeWarnings, ...reportWarnings];
    });

    const metricCards = computed(() => [
      {
        key: "grand",
        label: "Grand total",
        value: totals.value.grand_total_monthly_eur,
        detail: "All currently scanned components combined.",
      },
      {
        key: "instances",
        label: "Compute",
        value: totals.value.instances_monthly_eur,
        detail: `${safeArray(report.value?.instances).length} VM(s)`,
      },
      {
        key: "volumes",
        label: "Volumes",
        value: totals.value.volumes_monthly_eur,
        detail: `${safeArray(report.value?.volumes).length} root/data volume(s)`,
      },
      {
        key: "network",
        label: "Flexible IPs",
        value: totals.value.flexible_ips_monthly_eur,
        detail: `${safeArray(report.value?.flexible_ips).length} address(es)`,
      },
      {
        key: "object",
        label: "Object Storage",
        value: totals.value.object_storage_monthly_eur,
        detail: `${safeArray(report.value?.buckets).length} bucket(s)`,
      },
    ]);

    const mainPanels = computed(() => [
      {
        key: "cost",
        label: "Cost",
        caption: "Pricing, drivers, and inventory",
      },
      {
        key: "security",
        label: "Security Groups",
        caption: `${securityGroups.value.length} group(s) and attached VMs`,
      },
    ]);

    const tabs = computed(() => [
      {
        key: "instances",
        label: "Instances",
        count: safeArray(report.value?.instances).length,
      },
      {
        key: "volumes",
        label: "Volumes",
        count: safeArray(report.value?.volumes).length,
      },
      {
        key: "ips",
        label: "Flexible IPs",
        count: safeArray(report.value?.flexible_ips).length,
      },
      {
        key: "buckets",
        label: "Buckets",
        count: safeArray(report.value?.buckets).length,
      },
    ]);

    const matchesSearch = (haystack) => {
      const term = search.value.trim().toLowerCase();
      if (!term) {
        return true;
      }
      return haystack.toLowerCase().includes(term);
    };

    const filteredInstances = computed(() =>
      safeArray(report.value?.instances).filter((item) =>
        matchesSearch(
          [
            item.name,
            item.id,
            item.zone,
            item.commercial_type,
            item.public_ip,
            item.state,
          ]
            .filter(Boolean)
            .join(" ")
        )
      )
    );

    const filteredVolumes = computed(() =>
      safeArray(report.value?.volumes).filter((item) =>
        matchesSearch(
          [
            item.name,
            item.id,
            item.zone,
            item.volume_type,
            item.role,
            item.attached_server_name,
            item.attached_server_id,
            item.source_api,
          ]
            .filter(Boolean)
            .join(" ")
        )
      )
    );

    const filteredIps = computed(() =>
      safeArray(report.value?.flexible_ips).filter((item) =>
        matchesSearch(
          [item.id, item.address, item.zone, item.attached_server_id]
            .filter(Boolean)
            .join(" ")
        )
      )
    );

    const filteredBuckets = computed(() =>
      safeArray(report.value?.buckets).filter((item) =>
        matchesSearch(
          [item.name, item.region, JSON.stringify(item.storage_classes_gb)]
            .filter(Boolean)
            .join(" ")
        )
      )
    );

    const topDrivers = computed(() => {
      const grandTotal = safeNumber(totals.value.grand_total_monthly_eur) || 1;
      const drivers = [
        ...safeArray(report.value?.instances).map((item) => ({
          key: `instance-${item.id}`,
          kind: "instance",
          name: item.name,
          zone: item.zone,
          region: null,
          monthly_eur: safeNumber(item.monthly_eur),
        })),
        ...safeArray(report.value?.volumes).map((item) => ({
          key: `volume-${item.id}`,
          kind: item.role === "root" ? "root volume" : "data volume",
          name: item.name,
          zone: item.zone,
          region: null,
          monthly_eur: safeNumber(item.monthly_eur),
        })),
        ...safeArray(report.value?.flexible_ips).map((item) => ({
          key: `ip-${item.id}`,
          kind: "flexible ip",
          name: item.address || item.id,
          zone: item.zone,
          region: null,
          monthly_eur: safeNumber(item.monthly_eur),
        })),
        ...safeArray(report.value?.buckets).map((item) => ({
          key: `bucket-${item.name}`,
          kind: "bucket",
          name: item.name,
          zone: null,
          region: item.region,
          monthly_eur: safeNumber(item.monthly_eur),
        })),
      ]
        .filter((item) => item.monthly_eur > 0)
        .sort((left, right) => right.monthly_eur - left.monthly_eur)
        .slice(0, 8);

      return drivers.map((item) => ({
        ...item,
        percent: Math.max(
          8,
          Math.min(100, (item.monthly_eur / grandTotal) * 100)
        ),
      }));
    });

    const formatPortRange = (rule) => {
      const from = rule.dest_port_from;
      const to = rule.dest_port_to;
      if (from == null && to == null) {
        return "any-port";
      }
      if (to == null || from === to) {
        return `port ${from}`;
      }
      return `ports ${from}-${to}`;
    };

    const formatRule = (rule) => {
      const target = rule.dest_ip_range || rule.ip_range || "0.0.0.0/0";
      return [
        (rule.direction || "n/a").toUpperCase(),
        (rule.action || "n/a").toUpperCase(),
        (rule.protocol || "ANY").toUpperCase(),
        formatPortRange(rule),
        target,
      ].join(" / ");
    };

    const securitySummaryText = computed(() => {
      if (!securityGroups.value.length) {
        return "No security groups found in the current report.";
      }

      return securityGroups.value
        .map((group) => {
          const lines = [
            `Security Group: ${group.name} (${group.zone})`,
            `ID: ${group.id}`,
            `Description: ${group.description || "n/a"}`,
            `State: ${group.state || "n/a"} | Stateful: ${group.stateful ? "yes" : "no"} | Project default: ${group.project_default ? "yes" : "no"}`,
            `Default policies: inbound=${group.inbound_default_policy || "n/a"} | outbound=${group.outbound_default_policy || "n/a"} | default security=${group.enable_default_security ? "yes" : "no"}`,
            `VMs (${group.server_count}):`,
          ];

          if (group.servers.length) {
            group.servers.forEach((server) => {
              lines.push(
                `- ${server.name} | ${server.commercial_type || "n/a"} | ${server.state || "n/a"} | ${server.public_ip || "no-public-ip"}`
              );
            });
          } else {
            lines.push("- none");
          }

          lines.push(`Rules (${group.rule_count}):`);
          if (group.rules.length) {
            group.rules.forEach((rule) => {
              lines.push(`- ${formatRule(rule)}`);
            });
          } else {
            lines.push("- none");
          }

          return lines.join("\n");
        })
        .join("\n\n");
    });

    const money = (value) => `EUR ${safeNumber(value).toFixed(2)}`;
    const number = (value, digits = 0) => safeNumber(value).toFixed(digits);
    const percentage = (value) => {
      const total = safeNumber(totals.value.grand_total_monthly_eur);
      if (!total) {
        return 0;
      }
      return Math.max(6, Math.min(100, (safeNumber(value) / total) * 100));
    };

    const formatDate = (isoString) => {
      if (!isoString) {
        return "n/a";
      }
      return new Date(isoString).toLocaleString();
    };

    const compactId = (value) => {
      if (!value) {
        return "n/a";
      }
      if (value.length <= 16) {
        return value;
      }
      return `${value.slice(0, 8)}...${value.slice(-6)}`;
    };

    const yesNo = (value) => (value ? "yes" : "no");
    const badgeClass = (state) => (state ? "badge-ok" : "badge-warn");

    const renderStorageClasses = (value) => {
      if (!value || typeof value !== "object") {
        return "n/a";
      }
      return Object.entries(value)
        .map(([key, amount]) => `${key}: ${number(amount, 3)} GB`)
        .join(" | ");
    };

    const copySecuritySummary = async () => {
      try {
        await navigator.clipboard.writeText(securitySummaryText.value);
        copiedIntel.value = true;
        setTimeout(() => {
          copiedIntel.value = false;
        }, 1800);
      } catch (err) {
        error.value =
          err instanceof Error
            ? err.message
            : "Clipboard copy failed. You can still copy the text manually.";
      }
    };

    const loadExistingReport = async () => {
      error.value = "";
      const response = await fetch("/api/report", { cache: "no-store" });
      const payload = await response.json();
      status.value = payload.status || {};
      files.value = payload.files || {};
      report.value = payload.report;
    };

    const refreshNow = async () => {
      loading.value = true;
      error.value = "";
      try {
        const response = await fetch("/api/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: true }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Refresh failed.");
        }
        status.value = payload.status || {};
        files.value = payload.files || {};
        report.value = payload.report || null;
      } catch (err) {
        error.value = err instanceof Error ? err.message : String(err);
      } finally {
        loading.value = false;
      }
    };

    onMounted(async () => {
      try {
        await loadExistingReport();
      } catch (err) {
        error.value = err instanceof Error ? err.message : String(err);
      }
    });

    return {
      activeTab,
      appUrl,
      badgeClass,
      compactId,
      copiedIntel,
      copySecuritySummary,
      error,
      files,
      filteredBuckets,
      filteredInstances,
      filteredIps,
      filteredVolumes,
      formatDate,
      formatRule,
      loading,
      mainPanel,
      mainPanels,
      metricCards,
      money,
      number,
      percentage,
      refreshNow,
      renderStorageClasses,
      report,
      search,
      securityGroups,
      securitySummaryText,
      status,
      tabs,
      topDrivers,
      warnings,
      yesNo,
    };
  },
}).mount("#app");
