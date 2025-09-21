
const DEFAULT_RADIUS = 0.22;
const LAYOUT_MODES = ["saved", "radial", "grid"];
const NODE_TYPES = ["api", "event", "service", "store", "task", "ui"];
const NODE_STATUSES = ["active", "archived"];
const EDGE_TYPES = ["uses", "produces", "consumes", "depends"];

const NODE_COLORS = {
  api: "#38bdf8",
  event: "#fb923c",
  service: "#6366f1",
  store: "#34d399",
  task: "#facc15",
  ui: "#f472b6",
};

const EDGE_COLORS = {
  uses: "#38bdf8",
  produces: "#34d399",
  consumes: "#fb923c",
  depends: "#94a3b8",
};

function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value));
}

function normalizeNumber(value, fallback = 0.5) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function computeRadialLayout(count) {
  const angleStep = (2 * Math.PI) / Math.max(count, 1);
  const radius = 0.35;
  return Array.from({ length: count }, (_, index) => {
    const angle = index * angleStep;
    return {
      center_x: clamp(0.5 + radius * Math.cos(angle)),
      center_y: clamp(0.5 + radius * Math.sin(angle)),
      radius: DEFAULT_RADIUS,
    };
  });
}

function computeGridLayout(count) {
  const columns = Math.ceil(Math.sqrt(Math.max(count, 1)));
  const rows = Math.ceil(count / columns);
  const cellWidth = 1 / Math.max(columns, 1);
  const cellHeight = 1 / Math.max(rows, 1);
  return Array.from({ length: count }, (_, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    return {
      center_x: clamp(column * cellWidth + cellWidth / 2),
      center_y: clamp(row * cellHeight + cellHeight / 2),
      radius: Math.min(cellWidth, cellHeight) * 0.35,
    };
  });
}

function relativeToPixels(position, width, height) {
  return {
    x: clamp(normalizeNumber(position?.x, 0.5)) * width,
    y: clamp(normalizeNumber(position?.y, 0.5)) * height,
  };
}

function pixelsToRelative(position, width, height) {
  return {
    x: clamp(position.x / Math.max(width, 1e-6)),
    y: clamp(position.y / Math.max(height, 1e-6)),
  };
}

function projectToCircle(point, circle) {
  const dx = point.x - circle.center_x;
  const dy = point.y - circle.center_y;
  const distance = Math.sqrt(dx * dx + dy * dy);
  if (distance <= circle.radius || distance === 0) {
    return { x: point.x, y: point.y };
  }
  const scale = circle.radius / distance;
  return {
    x: circle.center_x + dx * scale,
    y: circle.center_y + dy * scale,
  };
}

function createLayers() {
  const container = document.getElementById("cy");
  if (!container) {
    return null;
  }
  container.innerHTML = "";
  const overlay = document.createElement("div");
  overlay.className = "spheres-overlay";
  const backdrop = document.createElement("div");
  backdrop.className = "sphere-backdrop";
  overlay.appendChild(backdrop);
  const graphLayer = document.createElement("div");
  graphLayer.className = "graph-layer";
  container.appendChild(overlay);
  container.appendChild(graphLayer);
  return { container, overlay, graphLayer, backdrop };
}

function buildCytoscape(container) {
  return cytoscape({
    container,
    autounselectify: false,
    boxSelectionEnabled: false,
    wheelSensitivity: 0.2,
    style: [
      {
        selector: "node",
        style: {
          width: 52,
          height: 52,
          shape: "round-rectangle",
          content: "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          color: "#0f172a",
          "font-size": 12,
          "text-wrap": "wrap",
          "text-max-width": 80,
          "background-color": "data(color)",
          "border-color": "#0f172a",
          "border-width": 2,
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-color": "#f8fafc",
          "border-width": 3,
        },
      },
      {
        selector: "edge",
        style: {
          width: 3,
          "line-color": "data(color)",
          "target-arrow-color": "data(color)",
          "target-arrow-shape": "triangle",
          "curve-style": "straight",
        },
      },
    ],
    layout: { name: "preset" },
  });
}

async function ensureOk(response, fallbackMessage) {
  if (response.ok) {
    return response;
  }
  let detail;
  try {
    const payload = await response.json();
    detail = payload?.detail;
  } catch (error) {
    detail = undefined;
  }
  throw new Error(detail || fallbackMessage);
}

function parseCommaSeparated(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

window.orgDashboard = function orgDashboard() {
  return {
    token: "",
    organizationId: "",
    members: [],
    groups: [],
    spheres: [],
    nodes: [],
    edges: [],
    renderedLayout: [],
    visibleSphereIds: new Set(),
    layoutMode: "saved",
    focusSphereId: null,
    notice: "",
    error: "",
    modals: {
      actions: false,
      node: false,
      edge: false,
      sphere: false,
      export: false,
    },
    filters: {
      sphereId: "",
      type: "",
      status: "",
      search: "",
    },
    nodeForm: {
      sphereId: "",
      label: "",
      nodeType: "service",
      status: "active",
      summary: "",
      links: "",
      owners: "",
    },
    edgeForm: {
      sphereId: "",
      relationType: "depends",
      source: "",
      target: "",
    },
    sphereForm: {
      name: "",
      description: "",
      color: "#38bdf8",
    },
    edgeCandidateNodes: [],
    exportData: "",
    activeNodeId: null,
    activeNode: null,
    overlay: null,
    backdrop: null,
    graphLayer: null,
    cy: null,

    get nodeTypeOptions() {
      return NODE_TYPES;
    },

    get nodeStatusOptions() {
      return NODE_STATUSES;
    },

    get edgeTypeOptions() {
      return EDGE_TYPES;
    },

    init() {
      const layers = createLayers();
      if (!layers) {
        console.warn("Не удалось инициализировать слои карты");
        return;
      }
      this.overlay = layers.overlay;
      this.backdrop = layers.backdrop;
      this.graphLayer = layers.graphLayer;
      this.cy = buildCytoscape(layers.graphLayer);
      if (this.backdrop) {
        this.backdrop.addEventListener("click", () => {
          if (this.focusSphereId !== null) {
            this.resetFocus();
          }
        });
      }
      this.cy.on("tap", (event) => {
        if (event.target === this.cy) {
          this.closeNodeCard();
        }
      });
      this.cy.on("tap", "node", (event) => {
        const id = Number(event.target.data("nodeId"));
        this.openNodeCard(id);
      });
      this.cy.on("dragfree", "node", (event) => {
        this.handleNodeDrag(event.target);
      });
      window.addEventListener("resize", () => {
        this.renderSpheres();
        this.renderGraph();
      });
      window.egida = window.egida || {};
      window.egida.dashboard = this;
    },

    authHeaders(extra = {}) {
      const headers = { ...extra };
      const token = this.token.trim();
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      return headers;
    },

    applyMapData(payload) {
      const spheres = payload?.spheres ?? [];
      const nodes = payload?.nodes ?? [];
      const edges = payload?.edges ?? [];
      const incomingIds = spheres.map((sphere) => sphere.id);
      const previous = new Set(this.visibleSphereIds);
      const nextVisible = new Set();
      if (previous.size) {
        incomingIds.forEach((id) => {
          if (previous.has(id)) {
            nextVisible.add(id);
          }
        });
      }
      if (!nextVisible.size) {
        incomingIds.forEach((id) => nextVisible.add(id));
      }
      this.spheres = spheres;
      this.nodes = nodes;
      this.edges = edges;
      this.visibleSphereIds = nextVisible;
      if (this.focusSphereId !== null && !incomingIds.includes(this.focusSphereId)) {
        this.focusSphereId = null;
      }
      if (!this.nodeForm.sphereId && this.spheres.length) {
        this.nodeForm.sphereId = String(this.spheres[0].id);
      }
      this.applyLayout(this.layoutMode || "saved");
      this.syncEdgeNodes();
      if (this.activeNodeId) {
        const current = this.nodes.find((node) => node.id === this.activeNodeId) || null;
        this.activeNode = current;
        if (!current) {
          this.activeNodeId = null;
        }
      }
    },

    buildMapParams(overrides = {}) {
      const orgId = overrides.organizationId ?? this.organizationId;
      if (!orgId) {
        return null;
      }
      const params = new URLSearchParams({
        organization_id: String(orgId).trim(),
      });
      const sphereFilter = overrides.sphereId ?? this.filters.sphereId;
      if (sphereFilter) {
        params.append("sphere_id", String(sphereFilter));
      }
      const typeFilter = overrides.nodeType ?? this.filters.type;
      if (typeFilter) {
        params.append("node_type", typeFilter);
      }
      const statusFilter = overrides.status ?? this.filters.status;
      if (statusFilter) {
        params.append("status", statusFilter);
      }
      const searchFilterRaw = overrides.search ?? this.filters.search;
      const searchFilter = typeof searchFilterRaw === "string" ? searchFilterRaw.trim() : "";
      if (searchFilter) {
        params.append("search", searchFilter);
      }
      return params;
    },

    async refreshMap(overrides = {}) {
      const params = this.buildMapParams(overrides);
      if (!params) {
        return false;
      }
      const headers = this.authHeaders();
      try {
        const response = await ensureOk(
          await fetch(`/api/map/?${params.toString()}`, { headers }),
          "Не удалось загрузить карту",
        );
        const data = await response.json();
        this.applyMapData(data);
        this.error = "";
        return true;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка загрузки карты";
        return false;
      }
    },

    mapDimensions() {
      return {
        width: this.graphLayer?.clientWidth || 1280,
        height: this.graphLayer?.clientHeight || 720,
      };
    },

    sphereById(id) {
      return this.spheres.find((sphere) => sphere.id === id) || null;


    },

    async loadOrg() {
      if (!this.token.trim() || !this.organizationId) {
        this.error = "Укажите токен и идентификатор организации";
        return;
      }
      this.error = "";
      this.notice = "";
      const orgId = String(this.organizationId).trim();
      const headers = this.authHeaders();
      const params = new URLSearchParams({ organization_id: orgId });
      try {
        const [mapRes, membersRes, groupsRes] = await Promise.all([
          fetch(`/api/map/?${params.toString()}`, { headers }),
          fetch(`/api/organizations/${orgId}/members`, { headers }),
          fetch(`/api/organizations/${orgId}/groups`, { headers }),
        ]);

        await ensureOk(mapRes, "Не удалось загрузить карту");
        await ensureOk(membersRes, "Не удалось загрузить участников");
        await ensureOk(groupsRes, "Не удалось загрузить группы");

        const mapData = await mapRes.json();
        this.applyMapData(mapData);
        this.members = await membersRes.json();
        this.groups = await groupsRes.json();
        this.filters = {
          sphereId: "",
          type: "",
          status: "",
          search: "",
        };
        this.notice = "Данные организации загружены";
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Не удалось загрузить организацию";
      }
    },

    applyLayout(mode) {
      const layoutMode = LAYOUT_MODES.includes(mode) ? mode : "saved";
      this.layoutMode = layoutMode;
      if (!this.spheres.length) {
        this.renderedLayout = [];
        this.renderSpheres();
        this.renderGraph();
        return;
      }
      let layout;
      if (layoutMode === "grid") {
        const computed = computeGridLayout(this.spheres.length);
        layout = this.spheres.map((sphere, index) => ({ id: sphere.id, ...computed[index] }));
      } else if (layoutMode === "radial") {
        const computed = computeRadialLayout(this.spheres.length);
        layout = this.spheres.map((sphere, index) => ({ id: sphere.id, ...computed[index] }));
      } else {
        const fallback = computeRadialLayout(this.spheres.length);
        layout = this.spheres.map((sphere, index) => ({
          id: sphere.id,
          center_x: clamp(normalizeNumber(sphere.center_x, fallback[index].center_x), 0, 1),
          center_y: clamp(normalizeNumber(sphere.center_y, fallback[index].center_y), 0, 1),
          radius: clamp(normalizeNumber(sphere.radius, fallback[index].radius), 0.08, 0.48),
        }));
      }
      this.renderedLayout = layout;
      this.renderSpheres();
      this.renderGraph();
    },

    toggleSphere(id) {
      const next = new Set(this.visibleSphereIds);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      if (!next.size) {
        this.spheres.forEach((sphere) => next.add(sphere.id));
      }
      this.visibleSphereIds = next;
      this.renderSpheres();
      this.renderGraph();
    },

    isSphereVisible(id) {
      return this.visibleSphereIds.has(id);
    },

    setLayoutMode(mode) {
      if (!LAYOUT_MODES.includes(mode)) {
        return;
      }
      this.applyLayout(mode);
    },

    focusSphere(id) {
      if (this.focusSphereId === id) {
        this.resetFocus();
        return;
      }
      this.focusSphereId = id;
      this.renderSpheres();
      this.renderGraph();
    },

    resetFocus() {
      this.focusSphereId = null;
      this.renderSpheres();
      this.renderGraph();
    },

    filteredNodes() {
      const query = (this.filters.search || "").trim().toLowerCase();
      return this.nodes.filter((node) => {
        if (this.filters.sphereId && Number(this.filters.sphereId) !== node.sphere_id) {
          return false;
        }
        if (this.filters.type && this.filters.type !== node.node_type) {
          return false;
        }
        if (this.filters.status && this.filters.status !== node.status) {
          return false;
        }
        if (this.focusSphereId !== null && node.sphere_id !== this.focusSphereId) {
          return false;
        }
        if (!this.visibleSphereIds.has(node.sphere_id)) {
          return false;
        }
        if (!query) {
          return true;
        }
        const haystack = [node.label, node.summary, ...(node.owners || [])]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      });
    },

    filteredEdges() {
      const allowed = new Set(this.filteredNodes().map((node) => node.id));
      return this.edges.filter(
        (edge) => allowed.has(edge.source_node_id) && allowed.has(edge.target_node_id),
      );
    },

    renderSpheres() {
      if (!this.overlay) {
        return;
      }
      this.overlay.innerHTML = "";
      if (!this.renderedLayout.length) {
        return;
      }
      const { width, height } = this.mapDimensions();
      this.renderedLayout.forEach((entry) => {
        if (!this.visibleSphereIds.has(entry.id)) {
          return;
        }
        const sphere = this.sphereById(entry.id);
        if (!sphere) {
          return;
        }
        const centerX = clamp(entry.center_x ?? 0.5, 0, 1);
        const centerY = clamp(entry.center_y ?? 0.5, 0, 1);
        const radius = clamp(entry.radius ?? DEFAULT_RADIUS, 0.08, 0.48);
        const pxRadius = radius * Math.min(width, height);

        const zone = document.createElement("div");
        zone.className = "sphere-zone";
        zone.dataset.sphereId = String(entry.id);
        zone.style.width = `${pxRadius * 2}px`;
        zone.style.height = `${pxRadius * 2}px`;
        zone.style.left = `${centerX * width - pxRadius}px`;
        zone.style.top = `${centerY * height - pxRadius}px`;
        zone.style.setProperty("--sphere-color", sphere.color || NODE_COLORS.service);

        if (this.focusSphereId !== null) {
          zone.style.opacity = this.focusSphereId === entry.id ? "1" : "0.25";
          if (this.focusSphereId === entry.id) {
            zone.classList.add("is-focused");
          }
        }

        const label = document.createElement("span");
        label.className = "sphere-label";
        label.textContent = sphere.name;
        zone.appendChild(label);

        zone.addEventListener("click", (event) => {
          event.stopPropagation();
          this.focusSphere(entry.id);
        });

        this.overlay.appendChild(zone);
      });
    },

    renderGraph() {
      if (!this.cy) {
        return;
      }
      const { width, height } = this.mapDimensions();
      const nodes = this.filteredNodes().map((node) => {
        const layout = this.renderedLayout.find((entry) => entry.id === node.sphere_id);
        let position = relativeToPixels(node.position || { x: 0.5, y: 0.5 }, width, height);
        if (layout) {
          const projected = projectToCircle(
            {
              x: position.x / width,
              y: position.y / height,
            },
            {
              center_x: clamp(layout.center_x, 0, 1),
              center_y: clamp(layout.center_y, 0, 1),
              radius: clamp(layout.radius, 0.08, 0.48),
            },
          );
          position = { x: projected.x * width, y: projected.y * height };
        }
        return {
          group: "nodes",
          data: {
            id: `node-${node.id}`,
            nodeId: node.id,
            label: node.label,
            node_type: node.node_type,
            status: node.status,
            sphereId: node.sphere_id,
            color: NODE_COLORS[node.node_type] || NODE_COLORS.service,
          },
          position,
        };
      });

      const edges = this.filteredEdges().map((edge) => ({
        group: "edges",
        data: {
          id: `edge-${edge.id}`,
          edgeId: edge.id,
          source: `node-${edge.source_node_id}`,
          target: `node-${edge.target_node_id}`,
          relationType: edge.relation_type,
          color: EDGE_COLORS[edge.relation_type] || EDGE_COLORS.depends,
        },
      }));

      this.cy.elements().remove();
      this.cy.add(nodes);
      this.cy.add(edges);
      this.cy.nodes().forEach((cyNode) => {
        cyNode.grabify();
      });
      if (this.focusSphereId !== null) {
        const focused = this.cy
          .nodes()
          .filter((cyNode) => Number(cyNode.data("sphereId")) === this.focusSphereId);
        if (focused.length) {
          this.cy.fit(focused, 80);
        }
      }
    },

    async applyFilters() {
      await this.refreshMap();
    },

    openModal(name) {
      this.modals[name] = true;
      if (name !== "actions") {
        this.modals.actions = false;
      }
      if (name === "node") {
        if (this.spheres.length && !this.nodeForm.sphereId) {
          this.nodeForm.sphereId = String(this.spheres[0].id);
        }
      }
      if (name === "edge") {
        this.syncEdgeNodes();
      }
      if (name === "sphere") {
        this.sphereForm = {
          name: "",
          description: "",
          color: "#38bdf8",
        };
      }
      if (name === "export") {
        this.loadExport();
      }
    },

    closeModal(name) {
      this.modals[name] = false;
      if (name !== "actions") {
        this.modals.actions = false;
      }
    },

    toggleActions() {
      this.modals.actions = !this.modals.actions;
    },

    syncEdgeNodes() {
      const sphereId = Number(this.edgeForm.sphereId);
      if (!sphereId) {
        this.edgeCandidateNodes = [];
        this.edgeForm.source = "";
        this.edgeForm.target = "";
        return;
      }
      this.edgeCandidateNodes = this.nodes.filter((node) => node.sphere_id === sphereId);
      this.edgeForm.source = "";
      this.edgeForm.target = "";
    },

    async createNode() {
      if (!this.nodeForm.sphereId || !this.nodeForm.label.trim()) {
        this.error = "Заполните сферу и название узла";
        return;
      }
      const sphereId = Number(this.nodeForm.sphereId);
      const layout = this.renderedLayout.find((entry) => entry.id === sphereId);
      const payload = {
        sphere_id: sphereId,
        label: this.nodeForm.label.trim(),
        node_type: this.nodeForm.nodeType,
        status: this.nodeForm.status,
        summary: this.nodeForm.summary,
        position: layout
          ? { x: layout.center_x ?? 0.5, y: layout.center_y ?? 0.5 }
          : { x: 0.5, y: 0.5 },
        metadata: {},
        links: parseCommaSeparated(this.nodeForm.links),
        owners: parseCommaSeparated(this.nodeForm.owners),
      };
      const headers = this.authHeaders({ "Content-Type": "application/json" });
      const label = payload.label;
      const preserved = {
        sphereId: this.nodeForm.sphereId,
        nodeType: this.nodeForm.nodeType,
        status: this.nodeForm.status,
      };
      try {
        await ensureOk(
          await fetch("/api/nodes", {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
          }),
          "Не удалось создать узел",
        );
        this.modals.node = false;
        this.nodeForm = {
          sphereId: preserved.sphereId,
          label: "",
          nodeType: preserved.nodeType,
          status: preserved.status,
          summary: "",
          links: "",
          owners: "",
        };
        await this.refreshMap();
        this.notice = `Узел "${label}" создан`;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка создания узла";
      }
    },

    async createEdge() {
      if (!this.edgeForm.sphereId || !this.edgeForm.source || !this.edgeForm.target) {
        this.error = "Выберите сферу и оба узла";
        return;
      }
      if (this.edgeForm.source === this.edgeForm.target) {
        this.error = "Нельзя соединить узел с самим собой";
        return;
      }
      const payload = {
        sphere_id: Number(this.edgeForm.sphereId),
        source_node_id: Number(this.edgeForm.source),
        target_node_id: Number(this.edgeForm.target),
        relation_type: this.edgeForm.relationType,
        metadata: {},
      };
      const headers = this.authHeaders({ "Content-Type": "application/json" });
      try {
        await ensureOk(
          await fetch("/api/edges", {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
          }),
          "Не удалось создать связь",
        );
        this.modals.edge = false;
        await this.refreshMap();
        this.notice = "Связь создана";
        this.edgeForm.source = "";
        this.edgeForm.target = "";
        this.syncEdgeNodes();
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка создания связи";
      }
    },

    async createSphere() {
      if (!this.sphereForm.name.trim()) {
        this.error = "Укажите название сферы";
        return;
      }
      const payload = {
        organization_id: Number(this.organizationId),
        name: this.sphereForm.name.trim(),
        description: this.sphereForm.description,
        color: this.sphereForm.color,
        group_ids: [],
      };
      const headers = this.authHeaders({ "Content-Type": "application/json" });
      const name = payload.name;
      try {
        await ensureOk(
          await fetch("/api/spheres", {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
          }),
          "Не удалось создать сферу",
        );
        this.modals.sphere = false;
        this.sphereForm = {
          name: "",
          description: "",
          color: "#38bdf8",
        };
        await this.refreshMap();
        this.notice = `Сфера "${name}" создана`;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка создания сферы";
      }
    },

    async loadExport() {
      const orgId = String(this.organizationId).trim();
      if (!orgId) {
        this.error = "Сначала загрузите организацию";
        return;
      }
      const headers = this.authHeaders();
      try {
        const response = await ensureOk(
          await fetch(`/api/graph/export?organization_id=${encodeURIComponent(orgId)}`, {
            headers,
          }),
          "Не удалось выполнить экспорт",
        );
        const data = await response.json();
        this.exportData = JSON.stringify(data, null, 2);
        this.notice = "Экспорт готов";
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка экспорта";
      }
    },

    async importGraph() {
      if (!this.exportData.trim()) {
        this.error = "Вставьте данные для импорта";
        return;
      }
      let payload;
      try {
        payload = JSON.parse(this.exportData);
      } catch (error) {
        this.error = "Некорректный JSON";
        return;
      }
      payload.organization_id = Number(this.organizationId);
      const headers = this.authHeaders({ "Content-Type": "application/json" });
      try {
        const response = await ensureOk(
          await fetch("/api/graph/import", {
            method: "POST",
            headers,
            body: JSON.stringify(payload),
          }),
          "Не удалось импортировать данные",
        );
        const data = await response.json();
        this.nodes = data.nodes;
        this.edges = data.edges;
        this.notice = "Граф импортирован";
        this.modals.export = false;
        await this.refreshMap();
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка импорта";
      }
    },

    openNodeCard(id) {
      const node = this.nodes.find((item) => item.id === id);
      if (!node) {
        return;
      }
      this.activeNodeId = id;
      this.activeNode = node;
    },

    closeNodeCard() {
      this.activeNodeId = null;
      this.activeNode = null;
    },

    async archiveNode() {
      if (!this.activeNodeId) {
        return;
      }
      await this.updateNode(this.activeNodeId, { status: "archived" });
      this.closeNodeCard();
    },

    async deleteNode() {
      if (!this.activeNodeId) {
        return;
      }
      const id = this.activeNodeId;
      const headers = this.authHeaders();
      try {
        await ensureOk(
          await fetch(`/api/nodes/${id}`, {
            method: "DELETE",
            headers,
          }),
          "Не удалось удалить узел",
        );
        this.closeNodeCard();
        await this.refreshMap();
        this.notice = "Узел удалён";
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка удаления узла";
      }
    },

    async updateNode(nodeId, payload) {
      const headers = this.authHeaders({ "Content-Type": "application/json" });
      try {
        await ensureOk(
          await fetch(`/api/nodes/${nodeId}`, {
            method: "PATCH",
            headers,
            body: JSON.stringify(payload),
          }),
          "Не удалось обновить узел",
        );
        await this.refreshMap();
        this.notice = "Узел обновлён";
      } catch (error) {
        this.error = error instanceof Error ? error.message : "Ошибка обновления узла";
      }
    },

    async handleNodeDrag(cyNode) {
      const id = Number(cyNode.data("nodeId"));
      const node = this.nodes.find((item) => item.id === id);
      if (!node) {
        return;
      }
      const { width, height } = this.mapDimensions();
      const relative = pixelsToRelative(cyNode.position(), width, height);
      const layout = this.renderedLayout.find((entry) => entry.id === node.sphere_id);
      let constrained = relative;
      if (layout) {
        constrained = projectToCircle(relative, {
          center_x: clamp(layout.center_x, 0, 1),
          center_y: clamp(layout.center_y, 0, 1),
          radius: clamp(layout.radius, 0.08, 0.48),
        });
      }
      const pixels = {
        x: constrained.x * width,
        y: constrained.y * height,
      };
      cyNode.position(pixels);
      await this.updateNode(id, { position: constrained });
    },
  };
};
