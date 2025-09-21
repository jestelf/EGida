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

const DASHBOARD_SELECTOR =
  '[data-egida-entry="org-dashboard"], [data-controller="org-dashboard"]';
const dashboardRegistry = new WeakMap();

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function normalizeStringArray(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return item.trim();
        }
        if (item === null || item === undefined) {
          return "";
        }
        return String(item).trim();
      })
      .filter((item) => item.length > 0);
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function normalizePositionPayload(raw) {
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return normalizePositionPayload(parsed);
    } catch (error) {
      return { x: 0.5, y: 0.5 };
    }
  }
  if (Array.isArray(raw)) {
    const [x, y] = raw;
    return {
      x: clamp(normalizeNumber(x, 0.5), 0, 1),
      y: clamp(normalizeNumber(y, 0.5), 0, 1),
    };
  }
  if (isRecord(raw)) {
    const candidate = raw;
    const xSource =
      candidate.x ??
      candidate.X ??
      candidate.left ??
      candidate.lng ??
      candidate.lon ??
      candidate.longitude ??
      candidate[0];
    const ySource =
      candidate.y ??
      candidate.Y ??
      candidate.top ??
      candidate.lat ??
      candidate.latitude ??
      candidate[1];
    return {
      x: clamp(normalizeNumber(xSource, 0.5), 0, 1),
      y: clamp(normalizeNumber(ySource, 0.5), 0, 1),
    };
  }
  if (typeof raw === "number") {
    const numeric = clamp(normalizeNumber(raw, 0.5), 0, 1);
    return { x: numeric, y: 0.5 };
  }
  return { x: 0.5, y: 0.5 };
}

function normalizeSpherePayload(raw) {
  if (!isRecord(raw)) {
    return null;
  }
  const id = Number(raw.id ?? raw.sphere_id ?? raw.sphereId);
  if (!Number.isFinite(id)) {
    return null;
  }
  const nameCandidate =
    typeof raw.name === "string"
      ? raw.name
      : typeof raw.label === "string"
        ? raw.label
        : undefined;
  const normalized = { ...raw, id };
  normalized.name = nameCandidate && nameCandidate.trim() ? nameCandidate.trim() : `Сфера ${id}`;
  normalized.center_x = clamp(normalizeNumber(raw.center_x ?? raw.centerX, 0.5), 0, 1);
  normalized.center_y = clamp(normalizeNumber(raw.center_y ?? raw.centerY, 0.5), 0, 1);
  normalized.radius = clamp(
    normalizeNumber(raw.radius ?? raw.sphereRadius ?? DEFAULT_RADIUS, DEFAULT_RADIUS),
    0.08,
    0.48,
  );
  if (typeof raw.color === "string") {
    normalized.color = raw.color;
  }
  if (!Array.isArray(raw.groups)) {
    normalized.groups = [];
  }
  const organizationId = Number(raw.organization_id ?? raw.organizationId ?? raw.org_id ?? raw.orgId);
  if (Number.isFinite(organizationId)) {
    normalized.organization_id = organizationId;
  }
  return normalized;
}

function normalizeNodePayload(raw) {
  if (!isRecord(raw)) {
    return null;
  }
  const id = Number(raw.id ?? raw.node_id ?? raw.nodeId);
  const sphereId = Number(raw.sphere_id ?? raw.sphereId);
  if (!Number.isFinite(id) || !Number.isFinite(sphereId)) {
    return null;
  }
  const labelCandidate =
    typeof raw.label === "string"
      ? raw.label
      : typeof raw.name === "string"
        ? raw.name
        : typeof raw.title === "string"
          ? raw.title
          : undefined;
  const nodeTypeRaw = (raw.node_type ?? raw.nodeType ?? raw.kind ?? "service").toString().toLowerCase();
  const nodeType = NODE_TYPES.includes(nodeTypeRaw) ? nodeTypeRaw : "service";
  const statusRaw = (raw.status ?? (raw.archived ? "archived" : "active") ?? "active")
    .toString()
    .toLowerCase();
  const status = NODE_STATUSES.includes(statusRaw) ? statusRaw : "active";
  let positionPayload = raw.position;
  if (!positionPayload || (isRecord(positionPayload) && !Object.keys(positionPayload).length)) {
    positionPayload = { x: raw.x, y: raw.y };
  }
  const position = normalizePositionPayload(positionPayload);
  const metadata = isRecord(raw.metadata) ? raw.metadata : {};
  const links = normalizeStringArray(raw.links ?? raw.links_json ?? metadata.links ?? []);
  const owners = normalizeStringArray(raw.owners ?? raw.owners_json ?? metadata.owners ?? []);
  const summary = typeof raw.summary === "string" ? raw.summary : "";
  const normalized = {
    ...raw,
    id,
    sphere_id: sphereId,
    label: labelCandidate && labelCandidate.trim() ? labelCandidate.trim() : `Узел ${id}`,
    node_type: nodeType,
    status,
    position,
    metadata,
    links,
    owners,
    summary,
  };
  const createdAt = raw.created_at ?? raw.createdAt;
  if (createdAt !== undefined) {
    normalized.created_at = createdAt;
  }
  return normalized;
}

function normalizeEdgePayload(raw) {
  if (!isRecord(raw)) {
    return null;
  }
  const id = Number(raw.id ?? raw.edge_id ?? raw.edgeId);
  const sphereId = Number(raw.sphere_id ?? raw.sphereId);
  const source = Number(raw.source_node_id ?? raw.sourceNodeId ?? raw.from_node_id ?? raw.fromNodeId);
  const target = Number(raw.target_node_id ?? raw.targetNodeId ?? raw.to_node_id ?? raw.toNodeId);
  if (!Number.isFinite(id) || !Number.isFinite(source) || !Number.isFinite(target)) {
    return null;
  }
  const relationRaw = (raw.relation_type ?? raw.relationType ?? raw.type ?? "depends")
    .toString()
    .toLowerCase();
  const relationType = EDGE_TYPES.includes(relationRaw) ? relationRaw : "depends";
  const metadata = isRecord(raw.metadata) ? raw.metadata : {};
  const normalized = {
    ...raw,
    id,
    sphere_id: Number.isFinite(sphereId) ? sphereId : null,
    source_node_id: source,
    target_node_id: target,
    relation_type: relationType,
    metadata,
  };
  if (!Number.isFinite(normalized.sphere_id)) {
    delete normalized.sphere_id;
  }
  return normalized;
}

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

function debounce(fn, delay) {
  let timer;
  return function debounced(...args) {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn.apply(this, args), delay);
  };
}

class OrgDashboard {
  constructor(root) {
    this.root = root;
    this.token = "";
    this.organizationId = "";
    this.members = [];
    this.groups = [];
    this.spheres = [];
    this.nodes = [];
    this.edges = [];
    this.renderedLayout = [];
    this.visibleSphereIds = new Set();
    this.layoutMode = "saved";
    this.focusSphereId = null;
    this.notice = "";
    this.error = "";
    this.modals = {
      actions: false,
      node: false,
      edge: false,
      sphere: false,
      export: false,
    };
    this.filters = {
      sphereId: "",
      type: "",
      status: "",
      search: "",
    };
    this.nodeForm = {
      sphereId: "",
      label: "",
      nodeType: "service",
      status: "active",
      summary: "",
      links: "",
      owners: "",
    };
    this.edgeForm = {
      sphereId: "",
      relationType: "depends",
      source: "",
      target: "",
    };
    this.sphereForm = {
      name: "",
      description: "",
      color: "#38bdf8",
    };
    this.edgeCandidateNodes = [];
    this.exportData = "";
    this.activeNodeId = null;
    this.activeNode = null;
    this.overlay = null;
    this.backdrop = null;
    this.graphLayer = null;
    this.cy = null;
    this.elements = {};
    this.modalOverlays = new Map();
    this.openModalButtons = [];
    this.closeModalButtons = [];
    this.debouncedApplyFilters = debounce(() => this.applyFilters(), 300);
    this.documentClickHandler = (event) => this.handleDocumentClick(event);
  }

  init() {
    this.cacheElements();
    this.populateStaticOptions();
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
    if (this.cy) {
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
    }
    window.addEventListener("resize", () => {
      this.renderSpheres();
      this.renderGraph();
    });
    this.setupEventListeners();
    this.updateUI();
    window.egida = window.egida || {};
    window.egida.dashboard = this;
  }

  cacheElements() {
    const root = this.root;
    this.elements = {
      tokenInput: root.querySelector("#token"),
      orgInput: root.querySelector("#org-id"),
      loadButton: root.querySelector('[data-action="load-org"]'),
      error: root.querySelector('[data-role="error"]'),
      notice: root.querySelector('[data-role="notice"]'),
      searchInput: root.querySelector('[data-role="search"]'),
      filterSphere: root.querySelector('[data-role="filter-sphere"]'),
      filterType: root.querySelector('[data-role="filter-type"]'),
      filterStatus: root.querySelector('[data-role="filter-status"]'),
      spheresPanel: root.querySelector('[data-role="spheres-panel"]'),
      sphereList: root.querySelector('[data-role="sphere-list"]'),
      layoutButtons: Array.from(root.querySelectorAll('[data-layout]')),
      quickList: root.querySelector('[data-role="quick-list"]'),
      fabButton: root.querySelector('[data-action="toggle-actions"]'),
      fabMenu: root.querySelector('[data-role="fab-menu"]'),
      nodeCard: root.querySelector('[data-role="node-card"]'),
      nodeTitle: root.querySelector('[data-role="node-title"]'),
      nodeType: root.querySelector('[data-role="node-type"]'),
      nodeStatus: root.querySelector('[data-role="node-status"]'),
      nodeSummary: root.querySelector('[data-role="node-summary"]'),
      nodeLinksSection: root.querySelector('[data-section="node-links"]'),
      nodeLinksList: root.querySelector('[data-role="node-links"]'),
      nodeOwnersSection: root.querySelector('[data-section="node-owners"]'),
      nodeOwnersList: root.querySelector('[data-role="node-owners"]'),
      closeNodeButton: root.querySelector('[data-action="close-node-card"]'),
      archiveButton: root.querySelector('[data-action="archive-node"]'),
      deleteButton: root.querySelector('[data-action="delete-node"]'),
      loadExportButton: root.querySelector('[data-action="load-export"]'),
      importGraphButton: root.querySelector('[data-action="import-graph"]'),
      createNodeButton: root.querySelector('[data-action="create-node"]'),
      createEdgeButton: root.querySelector('[data-action="create-edge"]'),
      createSphereButton: root.querySelector('[data-action="create-sphere"]'),
      nodeFormFields: {
        sphere: root.querySelector('[data-field="node-sphere"]'),
        label: root.querySelector('[data-field="node-label"]'),
        type: root.querySelector('[data-field="node-type"]'),
        status: root.querySelector('[data-field="node-status"]'),
        summary: root.querySelector('[data-field="node-summary"]'),
        links: root.querySelector('[data-field="node-links"]'),
        owners: root.querySelector('[data-field="node-owners"]'),
      },
      edgeFormFields: {
        sphere: root.querySelector('[data-field="edge-sphere"]'),
        type: root.querySelector('[data-field="edge-type"]'),
        source: root.querySelector('[data-field="edge-source"]'),
        target: root.querySelector('[data-field="edge-target"]'),
      },
      sphereFormFields: {
        name: root.querySelector('[data-field="sphere-name"]'),
        description: root.querySelector('[data-field="sphere-description"]'),
        color: root.querySelector('[data-field="sphere-color"]'),
      },
      exportField: root.querySelector('[data-field="export-data"]'),
    };
    this.modalOverlays = new Map();
    root.querySelectorAll('[data-modal]').forEach((overlay) => {
      const name = overlay.dataset.modal;
      if (name) {
        this.modalOverlays.set(name, overlay);
      }
    });
    this.openModalButtons = Array.from(root.querySelectorAll('[data-open-modal]'));
    this.closeModalButtons = Array.from(root.querySelectorAll('[data-close-modal]'));
  }

  populateStaticOptions() {
    const { filterType, filterStatus, nodeFormFields, edgeFormFields } = this.elements;
    if (filterType) {
      filterType.innerHTML = "";
      const allOption = document.createElement("option");
      allOption.value = "";
      allOption.textContent = "Все";
      filterType.appendChild(allOption);
      NODE_TYPES.forEach((type) => {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = type;
        filterType.appendChild(option);
      });
    }
    if (filterStatus) {
      filterStatus.innerHTML = "";
      const allOption = document.createElement("option");
      allOption.value = "";
      allOption.textContent = "Все";
      filterStatus.appendChild(allOption);
      NODE_STATUSES.forEach((status) => {
        const option = document.createElement("option");
        option.value = status;
        option.textContent = status;
        filterStatus.appendChild(option);
      });
    }
    if (nodeFormFields?.type) {
      nodeFormFields.type.innerHTML = "";
      NODE_TYPES.forEach((type) => {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = type;
        nodeFormFields.type.appendChild(option);
      });
    }
    if (nodeFormFields?.status) {
      nodeFormFields.status.innerHTML = "";
      NODE_STATUSES.forEach((status) => {
        const option = document.createElement("option");
        option.value = status;
        option.textContent = status;
        nodeFormFields.status.appendChild(option);
      });
    }
    if (edgeFormFields?.type) {
      edgeFormFields.type.innerHTML = "";
      EDGE_TYPES.forEach((type) => {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = type;
        edgeFormFields.type.appendChild(option);
      });
    }
  }

  setupEventListeners() {
    const {
      tokenInput,
      orgInput,
      loadButton,
      searchInput,
      filterSphere,
      filterType,
      filterStatus,
      layoutButtons,
      fabButton,
      closeNodeButton,
      archiveButton,
      deleteButton,
      loadExportButton,
      importGraphButton,
      createNodeButton,
      createEdgeButton,
      createSphereButton,
      nodeFormFields,
      edgeFormFields,
      sphereFormFields,
      exportField,
    } = this.elements;

    if (tokenInput) {
      tokenInput.addEventListener("input", (event) => {
        this.token = event.target.value;
      });
    }
    if (orgInput) {
      orgInput.addEventListener("input", (event) => {
        this.organizationId = event.target.value;
      });
    }
    if (loadButton) {
      loadButton.addEventListener("click", () => {
        this.loadOrg();
      });
    }
    if (searchInput) {
      searchInput.addEventListener("input", (event) => {
        this.filters.search = event.target.value || "";
        this.debouncedApplyFilters();
      });
    }
    if (filterSphere) {
      filterSphere.addEventListener("change", (event) => {
        this.filters.sphereId = event.target.value;
        this.applyFilters();
      });
    }
    if (filterType) {
      filterType.addEventListener("change", (event) => {
        this.filters.type = event.target.value;
        this.applyFilters();
      });
    }
    if (filterStatus) {
      filterStatus.addEventListener("change", (event) => {
        this.filters.status = event.target.value;
        this.applyFilters();
      });
    }
    if (layoutButtons?.length) {
      layoutButtons.forEach((button) => {
        button.addEventListener("click", () => {
          const mode = button.dataset.layout;
          if (mode) {
            this.setLayoutMode(mode);
          }
        });
      });
    }
    if (fabButton) {
      fabButton.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggleActions();
      });
    }
    document.addEventListener("click", this.documentClickHandler);
    this.openModalButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const name = button.dataset.openModal;
        if (name) {
          this.openModal(name);
        }
      });
    });
    this.closeModalButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const name = button.dataset.closeModal;
        if (name) {
          this.closeModal(name);
        }
      });
    });
    this.modalOverlays.forEach((overlay, name) => {
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
          this.closeModal(name);
        }
      });
    });
    if (closeNodeButton) {
      closeNodeButton.addEventListener("click", () => {
        this.closeNodeCard();
      });
    }
    if (archiveButton) {
      archiveButton.addEventListener("click", () => {
        this.archiveNode();
      });
    }
    if (deleteButton) {
      deleteButton.addEventListener("click", () => {
        this.deleteNode();
      });
    }
    if (createNodeButton) {
      createNodeButton.addEventListener("click", () => {
        this.createNode();
      });
    }
    if (createEdgeButton) {
      createEdgeButton.addEventListener("click", () => {
        this.createEdge();
      });
    }
    if (createSphereButton) {
      createSphereButton.addEventListener("click", () => {
        this.createSphere();
      });
    }
    if (loadExportButton) {
      loadExportButton.addEventListener("click", () => {
        this.loadExport();
      });
    }
    if (importGraphButton) {
      importGraphButton.addEventListener("click", () => {
        this.importGraph();
      });
    }
    if (nodeFormFields?.sphere) {
      nodeFormFields.sphere.addEventListener("change", (event) => {
        this.nodeForm.sphereId = event.target.value;
      });
    }
    if (nodeFormFields?.label) {
      nodeFormFields.label.addEventListener("input", (event) => {
        this.nodeForm.label = event.target.value;
      });
    }
    if (nodeFormFields?.type) {
      nodeFormFields.type.addEventListener("change", (event) => {
        this.nodeForm.nodeType = event.target.value;
      });
    }
    if (nodeFormFields?.status) {
      nodeFormFields.status.addEventListener("change", (event) => {
        this.nodeForm.status = event.target.value;
      });
    }
    if (nodeFormFields?.summary) {
      nodeFormFields.summary.addEventListener("input", (event) => {
        this.nodeForm.summary = event.target.value;
      });
    }
    if (nodeFormFields?.links) {
      nodeFormFields.links.addEventListener("input", (event) => {
        this.nodeForm.links = event.target.value;
      });
    }
    if (nodeFormFields?.owners) {
      nodeFormFields.owners.addEventListener("input", (event) => {
        this.nodeForm.owners = event.target.value;
      });
    }
    if (edgeFormFields?.sphere) {
      edgeFormFields.sphere.addEventListener("change", (event) => {
        this.edgeForm.sphereId = event.target.value;
        this.syncEdgeNodes();
      });
    }
    if (edgeFormFields?.type) {
      edgeFormFields.type.addEventListener("change", (event) => {
        this.edgeForm.relationType = event.target.value;
      });
    }
    if (edgeFormFields?.source) {
      edgeFormFields.source.addEventListener("change", (event) => {
        this.edgeForm.source = event.target.value;
      });
    }
    if (edgeFormFields?.target) {
      edgeFormFields.target.addEventListener("change", (event) => {
        this.edgeForm.target = event.target.value;
      });
    }
    if (sphereFormFields?.name) {
      sphereFormFields.name.addEventListener("input", (event) => {
        this.sphereForm.name = event.target.value;
      });
    }
    if (sphereFormFields?.description) {
      sphereFormFields.description.addEventListener("input", (event) => {
        this.sphereForm.description = event.target.value;
      });
    }
    if (sphereFormFields?.color) {
      sphereFormFields.color.addEventListener("input", (event) => {
        this.sphereForm.color = event.target.value;
      });
    }
    if (exportField) {
      exportField.addEventListener("input", (event) => {
        this.exportData = event.target.value;
      });
    }
  }

  handleDocumentClick(event) {
    if (!this.modals.actions) {
      return;
    }
    const { fabMenu, fabButton } = this.elements;
    if (!fabMenu) {
      return;
    }
    const target = event.target;
    if (fabMenu.contains(target)) {
      return;
    }
    if (fabButton && fabButton.contains(target)) {
      return;
    }
    this.modals.actions = false;
    this.updateUI();
  }

  updateUI() {
    this.updateFeedback();
    this.updateFilterSelects();
    this.updateSpheresPanelVisibility();
    this.renderSphereList();
    this.updateLayoutButtons();
    this.renderQuickList();
    this.updateFabMenu();
    this.renderNodeCard();
    this.renderModalVisibility();
    this.updateNodeFormFields();
    this.updateEdgeFormFields();
    this.updateSphereFormFields();
    this.updateExportField();
  }

  updateFeedback() {
    const { error, notice } = this.elements;
    if (error) {
      if (this.error) {
        error.textContent = this.error;
        error.hidden = false;
      } else {
        error.hidden = true;
        error.textContent = "";
      }
    }
    if (notice) {
      if (this.notice) {
        notice.textContent = this.notice;
        notice.hidden = false;
      } else {
        notice.hidden = true;
        notice.textContent = "";
      }
    }
  }

  updateFilterSelects() {
    const { filterSphere } = this.elements;
    if (!filterSphere) {
      return;
    }
    const currentValue = this.filters.sphereId || "";
    const options = [];
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "Все";
    options.push(allOption);
    this.spheres.forEach((sphere) => {
      const option = document.createElement("option");
      option.value = String(sphere.id);
      option.textContent = sphere.name;
      options.push(option);
    });
    const existing = Array.from(filterSphere.options).map((option) => option.value);
    const nextValues = options.map((option) => option.value);
    const changed =
      existing.length !== nextValues.length || existing.some((value, index) => value !== nextValues[index]);
    if (changed) {
      filterSphere.innerHTML = "";
      options.forEach((option) => filterSphere.appendChild(option));
    }
    if (nextValues.includes(currentValue)) {
      filterSphere.value = currentValue;
    } else {
      filterSphere.value = "";
      this.filters.sphereId = "";
    }
  }

  updateSpheresPanelVisibility() {
    const { spheresPanel } = this.elements;
    if (!spheresPanel) {
      return;
    }
    spheresPanel.hidden = this.spheres.length === 0;
  }

  renderSphereList() {
    const { sphereList } = this.elements;
    if (!sphereList) {
      return;
    }
    sphereList.innerHTML = "";
    if (!this.spheres.length) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Сферы пока не загружены";
      sphereList.appendChild(empty);
      return;
    }
    this.spheres.forEach((sphere) => {
      const item = document.createElement("li");
      if (this.focusSphereId === sphere.id) {
        item.classList.add("is-focused");
      }
      const name = document.createElement("span");
      name.className = "sphere-name";
      name.style.setProperty("--sphere-color", sphere.color || NODE_COLORS.service);
      name.textContent = sphere.name;
      item.appendChild(name);
      const toggle = document.createElement("div");
      toggle.className = "toggle";
      const focusButton = document.createElement("button");
      focusButton.type = "button";
      focusButton.className = "link";
      focusButton.textContent = this.focusSphereId === sphere.id ? "сбросить" : "фокус";
      focusButton.addEventListener("click", (event) => {
        event.stopPropagation();
        this.focusSphere(sphere.id);
      });
      const visibilityButton = document.createElement("button");
      visibilityButton.type = "button";
      visibilityButton.className = "link";
      visibilityButton.textContent = this.isSphereVisible(sphere.id) ? "скрыть" : "показать";
      visibilityButton.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggleSphere(sphere.id);
      });
      toggle.appendChild(focusButton);
      toggle.appendChild(visibilityButton);
      item.appendChild(toggle);
      sphereList.appendChild(item);
    });
  }

  updateLayoutButtons() {
    const { layoutButtons } = this.elements;
    if (!layoutButtons?.length) {
      return;
    }
    layoutButtons.forEach((button) => {
      const mode = button.dataset.layout;
      if (mode === this.layoutMode) {
        button.classList.add("is-active");
      } else {
        button.classList.remove("is-active");
      }
    });
  }

  renderQuickList() {
    const { quickList } = this.elements;
    if (!quickList) {
      return;
    }
    quickList.innerHTML = "";
    const nodes = this.filteredNodes().slice(0, 8);
    if (!nodes.length) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Нет узлов под условия";
      quickList.appendChild(empty);
      return;
    }
    nodes.forEach((node) => {
      const item = document.createElement("li");
      item.title = "Открыть карточку";
      item.addEventListener("click", () => {
        this.openNodeCard(node.id);
      });
      const dot = document.createElement("span");
      dot.className = "mini-dot";
      dot.style.setProperty("--dot-color", NODE_COLORS[node.node_type] || "#38bdf8");
      const box = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = node.label;
      const meta = document.createElement("p");
      meta.className = "muted";
      meta.textContent = `${node.node_type} · ${node.status}`;
      box.appendChild(title);
      box.appendChild(meta);
      item.appendChild(dot);
      item.appendChild(box);
      quickList.appendChild(item);
    });
  }

  updateFabMenu() {
    const { fabMenu } = this.elements;
    if (!fabMenu) {
      return;
    }
    fabMenu.hidden = !this.modals.actions;
  }

  renderNodeCard() {
    const {
      nodeCard,
      nodeTitle,
      nodeType,
      nodeStatus,
      nodeSummary,
      nodeLinksSection,
      nodeLinksList,
      nodeOwnersSection,
      nodeOwnersList,
    } = this.elements;
    if (!nodeCard) {
      return;
    }
    if (!this.activeNode) {
      nodeCard.hidden = true;
      return;
    }
    nodeCard.hidden = false;
    const node = this.activeNode;
    if (nodeTitle) {
      nodeTitle.textContent = node.label || "Узел";
    }
    if (nodeType) {
      nodeType.textContent = `Тип: ${node.node_type || "-"}`;
    }
    if (nodeStatus) {
      nodeStatus.textContent = `Статус: ${node.status || "-"}`;
    }
    if (nodeSummary) {
      nodeSummary.textContent = node.summary || "Описание отсутствует";
    }
    const links = Array.isArray(node.links) ? node.links : [];
    if (nodeLinksSection && nodeLinksList) {
      nodeLinksList.innerHTML = "";
      if (links.length) {
        links.forEach((link) => {
          const item = document.createElement("li");
          const anchor = document.createElement("a");
          anchor.href = link;
          anchor.target = "_blank";
          anchor.rel = "noreferrer";
          anchor.textContent = link;
          item.appendChild(anchor);
          nodeLinksList.appendChild(item);
        });
        nodeLinksSection.hidden = false;
      } else {
        nodeLinksSection.hidden = true;
      }
    }
    const owners = Array.isArray(node.owners) ? node.owners : [];
    if (nodeOwnersSection && nodeOwnersList) {
      nodeOwnersList.innerHTML = "";
      if (owners.length) {
        owners.forEach((owner) => {
          const item = document.createElement("li");
          item.textContent = owner;
          nodeOwnersList.appendChild(item);
        });
        nodeOwnersSection.hidden = false;
      } else {
        nodeOwnersSection.hidden = true;
      }
    }
  }

  renderModalVisibility() {
    this.modalOverlays.forEach((overlay, name) => {
      const isVisible = Boolean(this.modals[name]);
      overlay.hidden = !isVisible;
    });
  }

  updateNodeFormFields() {
    const { nodeFormFields } = this.elements;
    if (!nodeFormFields) {
      return;
    }
    if (nodeFormFields.sphere) {
      const options = [];
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Выберите сферу";
      options.push(placeholder);
      this.spheres.forEach((sphere) => {
        const option = document.createElement("option");
        option.value = String(sphere.id);
        option.textContent = sphere.name;
        options.push(option);
      });
      const existing = Array.from(nodeFormFields.sphere.options).map((option) => option.value);
      const nextValues = options.map((option) => option.value);
      const changed =
        existing.length !== nextValues.length || existing.some((value, index) => value !== nextValues[index]);
      if (changed) {
        nodeFormFields.sphere.innerHTML = "";
        options.forEach((option) => nodeFormFields.sphere.appendChild(option));
      }
      const candidate = this.nodeForm.sphereId || "";
      if (nextValues.includes(candidate)) {
        nodeFormFields.sphere.value = candidate;
      } else {
        nodeFormFields.sphere.value = "";
      }
    }
    if (nodeFormFields.type) {
      nodeFormFields.type.value = this.nodeForm.nodeType;
    }
    if (nodeFormFields.status) {
      nodeFormFields.status.value = this.nodeForm.status;
    }
    if (nodeFormFields.label) {
      nodeFormFields.label.value = this.nodeForm.label;
    }
    if (nodeFormFields.summary) {
      nodeFormFields.summary.value = this.nodeForm.summary;
    }
    if (nodeFormFields.links) {
      nodeFormFields.links.value = this.nodeForm.links;
    }
    if (nodeFormFields.owners) {
      nodeFormFields.owners.value = this.nodeForm.owners;
    }
  }

  updateEdgeFormFields() {
    const { edgeFormFields } = this.elements;
    if (!edgeFormFields) {
      return;
    }
    if (edgeFormFields.sphere) {
      const options = [];
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Выберите сферу";
      options.push(placeholder);
      this.spheres.forEach((sphere) => {
        const option = document.createElement("option");
        option.value = String(sphere.id);
        option.textContent = sphere.name;
        options.push(option);
      });
      const existing = Array.from(edgeFormFields.sphere.options).map((option) => option.value);
      const nextValues = options.map((option) => option.value);
      const changed =
        existing.length !== nextValues.length || existing.some((value, index) => value !== nextValues[index]);
      if (changed) {
        edgeFormFields.sphere.innerHTML = "";
        options.forEach((option) => edgeFormFields.sphere.appendChild(option));
      }
      const candidate = this.edgeForm.sphereId || "";
      if (nextValues.includes(candidate)) {
        edgeFormFields.sphere.value = candidate;
      } else {
        edgeFormFields.sphere.value = "";
      }
    }
    if (edgeFormFields.type) {
      edgeFormFields.type.value = this.edgeForm.relationType;
    }
    if (edgeFormFields.source) {
      const options = [];
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Выберите узел";
      options.push(placeholder);
      this.edgeCandidateNodes.forEach((node) => {
        const option = document.createElement("option");
        option.value = String(node.id);
        option.textContent = node.label;
        options.push(option);
      });
      const existing = Array.from(edgeFormFields.source.options).map((option) => option.value);
      const nextValues = options.map((option) => option.value);
      const changed =
        existing.length !== nextValues.length || existing.some((value, index) => value !== nextValues[index]);
      if (changed) {
        edgeFormFields.source.innerHTML = "";
        options.forEach((option) => edgeFormFields.source.appendChild(option));
      }
      if (nextValues.includes(this.edgeForm.source)) {
        edgeFormFields.source.value = this.edgeForm.source;
      } else {
        edgeFormFields.source.value = "";
        this.edgeForm.source = "";
      }
    }
    if (edgeFormFields.target) {
      const options = [];
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Выберите узел";
      options.push(placeholder);
      this.edgeCandidateNodes.forEach((node) => {
        const option = document.createElement("option");
        option.value = String(node.id);
        option.textContent = node.label;
        options.push(option);
      });
      const existing = Array.from(edgeFormFields.target.options).map((option) => option.value);
      const nextValues = options.map((option) => option.value);
      const changed =
        existing.length !== nextValues.length || existing.some((value, index) => value !== nextValues[index]);
      if (changed) {
        edgeFormFields.target.innerHTML = "";
        options.forEach((option) => edgeFormFields.target.appendChild(option));
      }
      if (nextValues.includes(this.edgeForm.target)) {
        edgeFormFields.target.value = this.edgeForm.target;
      } else {
        edgeFormFields.target.value = "";
        this.edgeForm.target = "";
      }
    }
  }

  updateSphereFormFields() {
    const { sphereFormFields } = this.elements;
    if (!sphereFormFields) {
      return;
    }
    if (sphereFormFields.name) {
      sphereFormFields.name.value = this.sphereForm.name;
    }
    if (sphereFormFields.description) {
      sphereFormFields.description.value = this.sphereForm.description;
    }
    if (sphereFormFields.color) {
      sphereFormFields.color.value = this.sphereForm.color;
    }
  }

  updateExportField() {
    const { exportField } = this.elements;
    if (!exportField) {
      return;
    }
    exportField.value = this.exportData;
  }

  authHeaders(extra = {}) {
    const headers = { ...extra };
    const token = this.token.trim();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }

  applyMapData(payload) {
    const rawSpheres = Array.isArray(payload?.spheres) ? payload.spheres : [];
    const rawNodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
    const rawEdges = Array.isArray(payload?.edges) ? payload.edges : [];
    const spheres = rawSpheres.map(normalizeSpherePayload).filter(Boolean);
    const nodes = rawNodes.map(normalizeNodePayload).filter(Boolean);
    const edges = rawEdges.map(normalizeEdgePayload).filter(Boolean);
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
    if (this.filters.sphereId && !incomingIds.includes(Number(this.filters.sphereId))) {
      this.filters.sphereId = "";
    }
    if (!this.nodeForm.sphereId && this.spheres.length) {
      this.nodeForm.sphereId = String(this.spheres[0].id);
    }
    if (this.edgeForm.sphereId && !incomingIds.includes(Number(this.edgeForm.sphereId))) {
      this.edgeForm.sphereId = "";
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
    this.updateUI();
  }

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
  }

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
      this.updateUI();
      return true;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка загрузки карты";
      this.updateUI();
      return false;
    }
  }

  mapDimensions() {
    return {
      width: this.graphLayer?.clientWidth || 1280,
      height: this.graphLayer?.clientHeight || 720,
    };
  }

  sphereById(id) {
    return this.spheres.find((sphere) => sphere.id === id) || null;
  }

  async loadOrg() {
    if (!this.token.trim() || !this.organizationId) {
      this.error = "Укажите токен и идентификатор организации";
      this.notice = "";
      this.updateUI();
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
      this.error = "";
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Не удалось загрузить организацию";
      this.notice = "";
      this.updateUI();
    }
  }

  applyLayout(mode) {
    const layoutMode = LAYOUT_MODES.includes(mode) ? mode : "saved";
    this.layoutMode = layoutMode;
    if (!this.spheres.length) {
      this.renderedLayout = [];
      this.renderSpheres();
      this.renderGraph();
      this.updateLayoutButtons();
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
    this.updateLayoutButtons();
  }

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
    this.updateUI();
  }

  isSphereVisible(id) {
    return this.visibleSphereIds.has(id);
  }

  setLayoutMode(mode) {
    if (!LAYOUT_MODES.includes(mode)) {
      return;
    }
    this.applyLayout(mode);
  }

  focusSphere(id) {
    if (this.focusSphereId === id) {
      this.resetFocus();
      return;
    }
    this.focusSphereId = id;
    this.renderSpheres();
    this.renderGraph();
    this.updateUI();
  }

  resetFocus() {
    this.focusSphereId = null;
    this.renderSpheres();
    this.renderGraph();
    this.updateUI();
  }

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
  }

  filteredEdges() {
    const allowed = new Set(this.filteredNodes().map((node) => node.id));
    return this.edges.filter(
      (edge) => allowed.has(edge.source_node_id) && allowed.has(edge.target_node_id),
    );
  }

  renderSpheres() {
    if (!this.overlay) {
      return;
    }
    this.overlay.innerHTML = "";
    if (this.backdrop) {
      this.overlay.appendChild(this.backdrop);
    }
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
  }

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
  }

  async applyFilters() {
    await this.refreshMap();
  }

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
    this.updateUI();
  }

  closeModal(name) {
    this.modals[name] = false;
    if (name !== "actions") {
      this.modals.actions = false;
    }
    this.updateUI();
  }

  toggleActions() {
    this.modals.actions = !this.modals.actions;
    this.updateUI();
  }

  syncEdgeNodes() {
    const sphereId = Number(this.edgeForm.sphereId);
    if (!sphereId) {
      this.edgeCandidateNodes = [];
      this.edgeForm.source = "";
      this.edgeForm.target = "";
      this.updateUI();
      return;
    }
    this.edgeCandidateNodes = this.nodes.filter((node) => node.sphere_id === sphereId);
    this.edgeForm.source = "";
    this.edgeForm.target = "";
    this.updateUI();
  }

  async createNode() {
    if (!this.nodeForm.sphereId || !this.nodeForm.label.trim()) {
      this.error = "Заполните сферу и название узла";
      this.updateUI();
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
      this.error = "";
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка создания узла";
      this.updateUI();
    }
  }

  async createEdge() {
    if (!this.edgeForm.sphereId || !this.edgeForm.source || !this.edgeForm.target) {
      this.error = "Выберите сферу и оба узла";
      this.updateUI();
      return;
    }
    if (this.edgeForm.source === this.edgeForm.target) {
      this.error = "Нельзя соединить узел с самим собой";
      this.updateUI();
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
      this.error = "";
      this.edgeForm.source = "";
      this.edgeForm.target = "";
      this.syncEdgeNodes();
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка создания связи";
      this.updateUI();
    }
  }

  async createSphere() {
    if (!this.sphereForm.name.trim()) {
      this.error = "Укажите название сферы";
      this.updateUI();
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
      this.error = "";
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка создания сферы";
      this.updateUI();
    }
  }

  async loadExport() {
    const orgId = String(this.organizationId).trim();
    if (!orgId) {
      this.error = "Сначала загрузите организацию";
      this.updateUI();
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
      this.error = "";
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка экспорта";
      this.updateUI();
    }
  }

  async importGraph() {
    if (!this.exportData.trim()) {
      this.error = "Вставьте данные для импорта";
      this.updateUI();
      return;
    }
    let payload;
    try {
      payload = JSON.parse(this.exportData);
    } catch (error) {
      this.error = "Некорректный JSON";
      this.updateUI();
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
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка импорта";
      this.updateUI();
    }
  }

  openNodeCard(id) {
    const node = this.nodes.find((item) => item.id === id);
    if (!node) {
      return;
    }
    this.activeNodeId = id;
    this.activeNode = node;
    this.updateUI();
  }

  closeNodeCard() {
    this.activeNodeId = null;
    this.activeNode = null;
    this.updateUI();
  }

  async archiveNode() {
    if (!this.activeNodeId) {
      return;
    }
    await this.updateNode(this.activeNodeId, { status: "archived" });
    this.closeNodeCard();
  }

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
      this.error = "";
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка удаления узла";
      this.updateUI();
    }
  }

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
      this.error = "";
      this.updateUI();
    } catch (error) {
      this.error = error instanceof Error ? error.message : "Ошибка обновления узла";
      this.updateUI();
    }
  }

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
  }
}

function collectDashboardRoots(scope) {
  const candidates = [];
  if (!scope) {
    return candidates;
  }
  if (scope instanceof HTMLElement && scope.matches(DASHBOARD_SELECTOR)) {
    candidates.push(scope);
  }
  if (typeof scope.querySelectorAll === "function") {
    scope.querySelectorAll(DASHBOARD_SELECTOR).forEach((element) => {
      if (element instanceof HTMLElement) {
        candidates.push(element);
      }
    });
  }
  const unique = [];
  const seen = new Set();
  candidates.forEach((element) => {
    if (!seen.has(element)) {
      seen.add(element);
      unique.push(element);
    }
  });
  return unique;
}

function initOrgDashboard(root) {
  if (!(root instanceof HTMLElement)) {
    return null;
  }
  if (dashboardRegistry.has(root)) {
    return dashboardRegistry.get(root) || null;
  }
  const instance = new OrgDashboard(root);
  try {
    instance.init();
    dashboardRegistry.set(root, instance);
    return instance;
  } catch (error) {
    dashboardRegistry.delete(root);
    console.error("Не удалось инициализировать org-dashboard", error);
    return null;
  }
}

function bootstrapOrgDashboards(scope = document) {
  return collectDashboardRoots(scope).map((root) => initOrgDashboard(root)).filter(Boolean);
}

function setupDashboardEntrypoints() {
  const runInitial = () => {
    bootstrapOrgDashboards(document);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runInitial, { once: true });
  } else {
    runInitial();
  }
  const handleHtmxEvent = (event) => {
    const target = event.target;
    const isFragment =
      typeof DocumentFragment !== "undefined" && target instanceof DocumentFragment;
    if (target instanceof HTMLElement || isFragment) {
      bootstrapOrgDashboards(target);
    }
  };
  document.addEventListener("htmx:load", handleHtmxEvent);
  document.addEventListener("htmx:afterSwap", handleHtmxEvent);
}

window.egida = window.egida || {};
window.egida.initOrgDashboard = initOrgDashboard;
window.egida.bootstrapOrgDashboards = bootstrapOrgDashboards;

setupDashboardEntrypoints();
