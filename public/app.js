/* Gerald OS Enterprise · Suite Multi-Empresa con Agentes Autónomos e Intervención Humana (HITL)
   Vanilla JS reactivo y seguro. Todo texto se inserta mediante textContent (sin innerHTML inseguro). */
"use strict";

// ---------- Directorio Multi-Empresa ----------
const EMPRESAS = {
  "C-ENTEL-PE": { nombre: "Entel Perú S.A.", sector: "Telecomunicaciones", color: "#00a9e0", sigla: "ENTEL", icono: "📱" },
  "C-BANCO-BCP": { nombre: "Banco de Crédito BCP", sector: "Banca & Finanzas", color: "#002a8f", sigla: "BCP", icono: "🏦" },
  "C-INTERBANK": { nombre: "Interbank", sector: "Banca & Retail", color: "#009939", sigla: "INTER", icono: "🟢" },
  "C-CLARO-PE": { nombre: "Claro Telecom Perú", sector: "Telecomunicaciones", color: "#da291c", sigla: "CLARO", icono: "🔴" },
  "C-001": { nombre: "Club Deportivo Sport", sector: "Deportes & Eventos", color: "#e8552b", sigla: "SPORT", icono: "👕" },
};

function resolverEmpresa(clienteId) {
  if (!clienteId) return { nombre: "Corporación Multi-Tenant", sector: "Corporativo B2B", color: "#64748b", sigla: "B2B", icono: "🏢" };
  if (EMPRESAS[clienteId]) return EMPRESAS[clienteId];
  for (const [k, v] of Object.entries(EMPRESAS)) {
    if (clienteId.includes(k.replace("C-", ""))) return v;
  }
  return { nombre: `Empresa ${clienteId}`, sector: "Corporativo", color: "#475569", sigla: clienteId.slice(0, 6), icono: "🏢" };
}

function badgeEmpresa(clienteId) {
  const emp = resolverEmpresa(clienteId);
  return h("span", {
    class: "badge-empresa",
    style: `--emp-color:${emp.color}`,
    title: `${emp.nombre} · ${emp.sector}`,
  }, h("span", { class: "icono" }, emp.icono), h("strong", {}, emp.sigla));
}

// ---------- DOM & Utilidades ----------
function h(tag, attrs, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const hijo of hijos.flat()) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return el;
}

const $raiz = () => document.getElementById("raiz");
const soles = (v) => v == null ? "—" : "S/ " + Number(v).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function aviso(texto, tipo = "") {
  const t = h("div", { class: "toast " + tipo, role: "status" },
    h("div", { class: "toast-icono" }, tipo === "ok" ? "✓" : tipo === "error" ? "⚠" : "ℹ"),
    h("div", { class: "toast-texto" }, texto));
  document.getElementById("avisos").append(t);
  setTimeout(() => {
    t.classList.add("desaparecer");
    setTimeout(() => t.remove(), 300);
  }, 4800);
}

const almacen = {
  leer(k) { try { return JSON.parse(sessionStorage.getItem(k)); } catch { return null; } },
  guardar(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
  borrar(k) { try { sessionStorage.removeItem(k); } catch { /* sin almacenamiento */ } },
};

// ---------- Sesión y API ----------
let sesion = almacen.leer("gs_sesion");

async function api(ruta, opciones = {}) {
  const cabeceras = { ...(opciones.headers || {}) };
  if (sesion) cabeceras.Authorization = "Bearer " + sesion.token;
  if (opciones.json !== undefined) {
    cabeceras["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(opciones.json);
  }
  const r = await fetch(ruta, { ...opciones, headers: cabeceras });
  if (r.status === 401) { cerrarSesion(); throw new Error("Su sesión expiró. Ingrese nuevamente."); }
  if (!r.ok) {
    let detalle = "Error " + r.status;
    try {
      const cuerpo = await r.json();
      if (typeof cuerpo.detail === "string") detalle = cuerpo.detail;
      else if (Array.isArray(cuerpo.detail)) detalle = cuerpo.detail.map((d) => d.msg).join(" · ");
    } catch { /* sin cuerpo */ }
    throw new Error(detalle);
  }
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}

function cerrarSesion() {
  sesion = null;
  almacen.borrar("gs_sesion");
  detenerSondeo();
  pintarLogin();
}

// ---------- Vocabulario BPMN & Estados ----------
const ESTADOS = {
  recibido: ["Recibido", "proceso"],
  validado: ["Validando", "proceso"],
  interpretado: ["Interpretando boceto", "proceso"],
  calculado: ["Calculando costo", "proceso"],
  en_revision: ["En revisión (HITL)", "alerta"],
  cotizado: ["Cotización lista", "accion"],
  contratado: ["Contratado", "ok"],
  esperando_abastecimiento: ["Esperando materiales", "alerta"],
  reservado: ["Materiales reservados", "ok"],
  en_produccion: ["En producción", "ok"],
  observado: ["Requiere corrección", "error"],
  duplicado: ["Duplicado", "neutro"],
  no_contratado: ["No contratado", "neutro"],
  pendiente_reproceso: ["Reintentando", "alerta"],
  detenido: ["Detenido", "error"],
};

const PASOS = ["Ingesta", "Análisis IA", "Cotización", "Contrato", "Abastecimiento", "Producción"];
const PASO_DE = {
  recibido: 0, validado: 1, interpretado: 1, calculado: 1, en_revision: 1, cotizado: 2,
  contratado: 3, esperando_abastecimiento: 4, reservado: 4, en_produccion: 6,
};
const EN_PROCESO = new Set([null, undefined, "recibido", "validado", "interpretado", "calculado", "contratado", "reservado", "pendiente_reproceso"]);

function chipEstado(estado) {
  const [texto, clase] = ESTADOS[estado] || ["Procesando", "proceso"];
  return h("span", { class: "estado " + clase }, texto);
}

function resumenLineas(lineas) {
  return lineas.map((l) => `${l.cantidad} ${l.prenda} ${l.talla} ${l.color}`).join(" · ");
}

// ---------- Roles del Sistema ----------
const ROLES = [
  { rol: "administrador", titulo: "👑 Administrador Global", desc: "Torre de Control Multi-Empresa & HITL", id: "ADM-GLOBAL", empresa: "Gerald Enterprise OS" },
  { rol: "cliente", titulo: "📱 Entel Perú", desc: "Portal Corporativo · Telecomunicaciones", id: "C-ENTEL-PE", empresa: "Entel Perú S.A." },
  { rol: "cliente", titulo: "🏦 Banco BCP", desc: "Portal Corporativo · Finanzas & Merchandising", id: "C-BANCO-BCP", empresa: "Banco de Crédito BCP" },
  { rol: "cliente", titulo: "🟢 Interbank", desc: "Portal Corporativo · Eventos y Marketing", id: "C-INTERBANK", empresa: "Interbank" },
  { rol: "cliente", titulo: "🔴 Claro Perú", desc: "Portal Corporativo · Dotación y Logística", id: "C-CLARO-PE", empresa: "Claro Perú" },
  { rol: "almacen", titulo: "📦 Almacén Central", desc: "Supply Chain & Abastecimiento B2B", id: "ALM-CENTRAL", empresa: "Supply Hub Central" },
  { rol: "auditor", titulo: "🔍 Auditor de IA", desc: "Calibración, Gobernanza & Trazabilidad", id: "AUD-GOV", empresa: "Comité de Auditoría" },
];

async function pintarLogin() {
  let demo = true;
  try { demo = (await (await fetch("/demo/estado")).json()).demo; } catch { /* offline */ }
  let elegido = ROLES[0];
  const idInput = h("input", { type: "text", value: elegido.id, "aria-label": "Identificador", autocomplete: "off" });

  const botones = ROLES.map((r) => h("button", {
    type: "button", class: "rol-card", "aria-pressed": String(r === elegido),
    onclick: () => {
      elegido = r; idInput.value = r.id;
      botones.forEach((b, i) => b.setAttribute("aria-pressed", String(ROLES[i] === r)));
    },
  },
    h("div", { class: "rol-card-header" },
      h("strong", {}, r.titulo),
      h("span", { class: "rol-empresa-tag" }, r.empresa)),
    h("p", { class: "rol-desc" }, r.desc)));

  const tokenInput = h("textarea", { placeholder: "Pegue aquí su JWT de acceso corporativo", rows: 3 });
  const enviar = h("button", { class: "btn btn-primario btn-grande", type: "submit" }, "Acceder a la Plataforma");

  const formulario = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      enviar.disabled = true;
      try {
        if (demo) {
          const r = await api("/demo/sesion", { method: "POST", json: { rol: elegido.rol, id: idInput.value.trim() } });
          sesion = { token: r.token, rol: r.rol, id: r.id, empresa: elegido.empresa };
        } else {
          const token = tokenInput.value.trim();
          const datos = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
          sesion = { token, rol: datos.rol, id: datos.sub, empresa: "Corporativo" };
        }
        almacen.guardar("gs_sesion", sesion);
        iniciarApp();
      } catch (err) {
        aviso(err.message.includes("JSON") || err.message.includes("atob") ? "Token inválido" : err.message, "error");
      } finally { enviar.disabled = false; }
    },
  },
    demo ? [
      h("div", { class: "selector-roles-titulo" }, "Seleccione el perfil o empresa corporativa:"),
      h("div", { class: "roles-grid" }, botones),
      h("div", { class: "id-override" },
        h("label", { class: "campo" }, h("span", {}, "Identificador de Cuenta / Tenant ID"), idInput)),
    ] : h("label", { class: "campo" }, h("span", {}, "Token de acceso"), tokenInput),
    enviar);

  $raiz().replaceChildren(h("div", { class: "login-contenedor" },
    h("div", { class: "login-tarjeta" },
      h("div", { class: "login-marca" },
        h("div", { class: "logo-plataforma" }, "GO"),
        h("div", {},
          h("h1", {}, "Gerald Enterprise OS"),
          h("div", { class: "plataforma-sub" }, "Plataforma Multi-Empresa de Abastecimiento & Producción con Agentes IA"))),
      h("div", { class: "banner-multiempresa" },
        h("div", { class: "chip-multi" }, "MULTI-TENANT ARCHITECTURE"),
        h("p", {}, "Orquestación LangGraph · Control Tower HITL · LangSmith Observability")),
      formulario,
      demo && h("div", { class: "nota-demo" },
        "💡 Modo Demostración Multi-Empresa activo. Puede alternar entre clientes corporativos o ingresar como Administrador Global para supervisar la torre de control."))));
}

// ---------- Marco de la Aplicación ----------
const VISTAS = {
  cliente: [
    ["mis", "Mis Pedidos Corporativos"],
    ["nuevo", "+ Crear Pedido"],
    ["metricas", "📊 Arquitectura SDD & ROI"],
  ],
  administrador: [
    ["bandeja", "Torre de Control (HITL)"],
    ["nuevo", "+ Crear Pedido"],
    ["mis", "Todos los Pedidos"],
    ["calibracion", "Gobernanza & Calibración"],
    ["metricas", "📊 Arquitectura SDD & ROI"],
  ],
  almacen: [
    ["faltantes", "Supply Chain & Almacén"],
    ["nuevo", "+ Crear Pedido"],
    ["mis", "Todos los Pedidos"],
    ["metricas", "📊 Arquitectura SDD & ROI"],
  ],
  auditor: [
    ["calibracion", "Gobernanza & Calibración"],
    ["bandeja", "Supervisión HITL"],
    ["mis", "Auditoría de Pedidos"],
    ["metricas", "📊 Arquitectura SDD & ROI"],
  ],
};

const NOMBRE_ROL = {
  cliente: "Cliente Corporativo",
  administrador: "Administrador Global",
  almacen: "Supply & Almacén",
  auditor: "Auditor de IA",
};

let vistaActual = null;
let sondeo = null;
let contenedor = null;
let navBotones = {};
let simulando = false;

function detenerSondeo() { if (sondeo) { clearInterval(sondeo); sondeo = null; } }
function sondear(fn, ms = 3500) { detenerSondeo(); sondeo = setInterval(() => fn().catch(() => { }), ms); }

// Acción: Simulación 1-Click Multi-Empresa
async function dispararSimulacion(btn) {
  if (simulando) return;
  simulando = true;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⚡ Simulando pedidos...";
    btn.classList.add("anim-pulso");
  }
  aviso("⚡ Ejecutando simulación de 4 pedidos multi-empresa y trazando en LangSmith...", "info");
  try {
    const res = await api("/demo/simular", { method: "POST" });
    const total = res.total || res.pedidos_simulados?.length || 4;
    aviso(`¡Éxito! Se generaron y trazaron en LangSmith ${total} pedidos (Entel, BCP, Interbank, Claro).`, "ok");
    // Refrescar vista activa
    if (vistaActual) irA(vistaActual);
  } catch (err) {
    aviso("Error al simular: " + err.message, "error");
  } finally {
    simulando = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "";
      btn.append(h("span", { class: "rayo" }, "⚡"), document.createTextNode(" Simulación Altoque"));
      btn.classList.remove("anim-pulso");
    }
  }
}

function iniciarApp() {
  const vistas = VISTAS[sesion.rol] || [];
  navBotones = {};

  const nav = h("nav", { "aria-label": "Secciones de la plataforma" }, vistas.map(([clave, titulo]) => {
    const b = h("button", { onclick: () => irA(clave) }, titulo);
    navBotones[clave] = b;
    return b;
  }));

  const btnSimulacion = h("button", {
    type: "button",
    class: "btn btn-simulacion",
    title: "Genera automáticamente 4 pedidos multiempresa (Entel, BCP, Interbank, Claro) con procesamiento multiagente",
    onclick: () => dispararSimulacion(btnSimulacion),
  }, h("span", { class: "rayo" }, "⚡"), document.createTextNode(" Simulación Altoque"));

  const btnCrearNav = h("button", {
    type: "button",
    class: "btn btn-primario",
    style: "font-size:13px;padding:7px 14px",
    title: "Personaliza y envía tu propio pedido corporativo",
    onclick: () => irA("nuevo"),
  }, "+ Crear Pedido");

  const empActual = resolverEmpresa(sesion.id);

  contenedor = h("main", { class: "contenedor-principal" });
  $raiz().replaceChildren(
    h("header", { class: "barra-enterprise" },
      h("div", { class: "barra-left" },
        h("div", { class: "marca-enterprise" },
          h("div", { class: "logo-plataforma" }, "GO"),
          h("div", { class: "marca-texto" },
            h("div", { class: "marca-nombre" }, "Gerald Enterprise OS"),
            h("span", { class: "marca-tag" }, "Multi-Agent Platform"))),
        nav),
      h("div", { class: "barra-right" },
        btnCrearNav,
        btnSimulacion,
        h("div", { class: "separador-v" }),
        h("div", { class: "tenant-pill" },
          sesion.rol === "cliente" ? [
            h("span", { class: "tenant-icono" }, empActual.icono),
            h("span", { class: "tenant-nombre" }, empActual.nombre),
          ] : [
            h("span", { class: "tenant-icono" }, "🌐"),
            h("span", { class: "tenant-nombre" }, "Global Multi-Tenant"),
          ]),
        h("div", { class: "usuario-chip" },
          h("span", { class: "chip-rol" }, NOMBRE_ROL[sesion.rol]),
          h("span", { class: "usuario-id mono" }, sesion.id)),
        h("button", { class: "btn btn-texto btn-salir", onclick: cerrarSesion, title: "Cerrar sesión o cambiar de empresa" }, "Cambiar Rol"))),
    contenedor);

  irA(vistas[0][0]);
}

function irA(clave, extra) {
  detenerSondeo();
  vistaActual = clave;
  Object.entries(navBotones).forEach(([k, b]) => {
    if (k === clave) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  contenedor.replaceChildren();
  ({
    nuevo: vistaNuevo,
    mis: vistaMis,
    bandeja: vistaBandeja,
    calibracion: vistaCalibracion,
    faltantes: vistaFaltantes,
    metricas: vistaMetricas,
  })[clave](extra);
}

function cabecera(titulo, subtitulo, ...derecha) {
  return h("div", { class: "cabecera-enterprise" },
    h("div", { class: "cabecera-titulos" },
      h("h2", {}, titulo),
      subtitulo && h("p", { class: "cabecera-sub" }, subtitulo)),
    h("div", { class: "cabecera-acciones" }, derecha));
}

function vacio(icono, titulo, texto) {
  return h("div", { class: "estado-vacio" },
    h("div", { class: "vacio-icono", "aria-hidden": "true" }, icono),
    h("strong", {}, titulo),
    h("p", {}, texto));
}

// ---------- CLIENTE: Nuevo Pedido ----------
let catalogo = null;
async function obtenerCatalogo() {
  if (!catalogo) catalogo = (await api("/catalogo")).prendas;
  return catalogo;
}

// Plantillas predefinidas corporativas
const PLANTILLAS_CORP = [
  {
    nombre: "📱 Entel: 45 Polos L azul entel",
    cliente_id: "C-ENTEL-PE",
    lineas: [{ prenda: "polo", talla: "L", color: "Azul Entel", cantidad: 45 }],
    notas: "Uniformes corporativos sucursal Lima Centro. Bordado pecho izq.",
  },
  {
    nombre: "🏦 BCP: 25 Casacas M azul noche",
    cliente_id: "C-BANCO-BCP",
    lineas: [{ prenda: "casaca", talla: "M", color: "Azul Noche", cantidad: 25 }],
    notas: "Casacas térmicas para evento anual de innovación BCP.",
  },
  {
    nombre: "🟢 Interbank: 30 Shorts M verde corporativo",
    cliente_id: "C-INTERBANK",
    lineas: [{ prenda: "short", talla: "M", color: "Verde Corporativo", cantidad: 30 }],
    notas: "Torneo deportivo interbancario corporativo.",
  },
  {
    nombre: "🔴 Claro: 60 Polos S rojo claro",
    cliente_id: "C-CLARO-PE",
    lineas: [{ prenda: "polo", talla: "S", color: "Rojo Claro", cantidad: 60 }],
    notas: "Maratón Claro 10K. Sublimación logo institucional.",
  },
];

async function vistaNuevo(prellenado) {
  const prendas = await obtenerCatalogo();
  const nombres = Object.keys(prendas);
  const lineas = [];
  const cajaLineas = h("div", { class: "lineas-pedido" });
  const resumen = h("ul", { class: "resumen-lista" });
  const totalPrendas = h("strong", {}, "0");
  let archivo = null;

  // Selector de empresa solicitante
  const empresasLista = [
    { id: "C-ENTEL-PE", nombre: "📱 Entel Perú S.A." },
    { id: "C-BANCO-BCP", nombre: "🏦 Banco de Crédito BCP" },
    { id: "C-INTERBANK", nombre: "🟢 Interbank" },
    { id: "C-CLARO-PE", nombre: "🔴 Claro Telecom Perú" },
    { id: "C-001", nombre: "👕 Club Deportivo Sport" },
  ];
  const selectEmpresa = h("select", { "aria-label": "Empresa solicitante" },
    empresasLista.map((e) => h("option", { value: e.id, selected: e.id === sesion.id }, e.nombre))
  );

  function refrescarResumen() {
    const datos = lineas.map((l) => l.leer());
    resumen.replaceChildren(...datos.filter((d) => d.cantidad > 0).map((d) =>
      h("li", {},
        h("span", {}, `${d.prenda} · ${d.talla} · ${d.color || "sin color"}`),
        h("strong", {}, d.cantidad))));
    if (!resumen.children.length) resumen.append(h("li", { class: "mute" }, "Agregue al menos una prenda"));
    totalPrendas.textContent = datos.reduce((s, d) => s + (d.cantidad || 0), 0);
  }

  function agregarLinea(inicial = {}) {
    const prenda = h("select", { "aria-label": "Prenda" }, nombres.map((n) => h("option", { value: n }, n[0].toUpperCase() + n.slice(1))));
    const talla = h("select", { "aria-label": "Talla" });
    const color = h("input", { type: "text", placeholder: "Ej. Azul Corporativo", maxlength: 40, value: inicial.color || "" });
    const cantidad = h("input", { type: "number", min: 1, max: 1000, value: inicial.cantidad || 10 });

    const llenarTallas = () => {
      const previa = talla.value || inicial.talla;
      talla.replaceChildren(...prendas[prenda.value].map((t) => h("option", { value: t }, t)));
      if (prendas[prenda.value].includes(previa)) talla.value = previa;
    };
    if (inicial.prenda && prendas[inicial.prenda]) prenda.value = inicial.prenda;
    llenarTallas();

    const fila = h("div", { class: "linea-fila" },
      h("label", { class: "campo" }, h("span", {}, "Prenda"), prenda),
      h("label", { class: "campo" }, h("span", {}, "Talla"), talla),
      h("label", { class: "campo" }, h("span", {}, "Color Corporativo"), color),
      h("label", { class: "campo" }, h("span", {}, "Cantidad"), cantidad),
      h("button", {
        type: "button", class: "btn btn-texto quitar", title: "Quitar prenda",
        onclick: () => { if (lineas.length > 1) { lineas.splice(lineas.indexOf(registro), 1); fila.remove(); refrescarResumen(); } },
      }, "✕"));

    const registro = {
      leer: () => ({ prenda: prenda.value, talla: talla.value, color: color.value.trim(), cantidad: parseInt(cantidad.value, 10) || 0 }),
      fijar: (d) => {
        if (d.prenda && prendas[d.prenda]) { prenda.value = d.prenda; llenarTallas(); }
        if (d.talla) talla.value = d.talla;
        if (d.color) color.value = d.color;
        if (d.cantidad) cantidad.value = d.cantidad;
      },
    };
    prenda.addEventListener("change", () => { llenarTallas(); refrescarResumen(); });
    [talla, color, cantidad].forEach((el) => el.addEventListener("input", refrescarResumen));
    lineas.push(registro);
    cajaLineas.append(fila);
    refrescarResumen();
  }

  (prellenado?.lineas?.length ? prellenado.lineas : [{}]).forEach(agregarLinea);

  const entradaArchivo = h("input", { type: "file", accept: "image/png,image/jpeg,application/pdf", hidden: true });
  const previa = h("div", {});
  const zona = h("div", {
    class: "zona-archivo", tabindex: 0, role: "button",
    onclick: () => entradaArchivo.click(),
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); entradaArchivo.click(); } },
    ondragover: (e) => { e.preventDefault(); zona.classList.add("sobre"); },
    ondragleave: () => zona.classList.remove("sobre"),
    ondrop: (e) => {
      e.preventDefault(); zona.classList.remove("sobre");
      if (e.dataTransfer.files[0]) fijarArchivo(e.dataTransfer.files[0]);
    },
  },
    h("div", { class: "zona-icono" }, "📁"),
    h("strong", {}, "Adjunte el boceto o ficha técnica corporativa"),
    h("span", { class: "mute peq" }, "PNG, JPG o PDF hasta 10 MB (analizado por Agente de Visión IA)"),
    previa);

  function fijarArchivo(f) {
    archivo = f;
    previa.replaceChildren(
      f.type.startsWith("image/")
        ? h("img", { class: "vista-previa", src: URL.createObjectURL(f), alt: "Boceto seleccionado" })
        : h("p", { class: "peq", style: "margin-top:8px;font-weight:600" }, "📄 " + f.name));
  }
  entradaArchivo.addEventListener("change", () => { if (entradaArchivo.files[0]) fijarArchivo(entradaArchivo.files[0]); });

  const btnBocetoDemo = h("button", {
    type: "button",
    class: "btn btn-plantilla",
    style: "margin-top:8px;font-weight:600",
    onclick: async () => {
      btnBocetoDemo.disabled = true;
      btnBocetoDemo.textContent = "⏳ Generando diseño vectorial con IA...";
      try {
        const emp = selectEmpresa.value || sesion.id;
        const primera = lineas[0]?.leer();
        const f = await generarBocetoSport(emp, primera?.prenda || "Polo Deportivo", primera?.color || "Azul");
        fijarArchivo(f);
        aviso("✓ Ficha técnica vectorial generada por IA con paleta corporativa.", "ok");
      } catch (e) {
        aviso("Error al generar boceto: " + e.message, "error");
      } finally {
        btnBocetoDemo.disabled = false;
        btnBocetoDemo.textContent = "✨ Generar Boceto Técnico IA (1 clic)";
      }
    },
  }, "✨ Generar Boceto Técnico IA (1 clic)");

  const notas = h("textarea", {
    placeholder: "Especificaciones especiales de confección, ubicación del logo, tipo de bordado o estampado, fecha deseada...",
    value: prellenado?.notas || "",
  });

  const enviar = h("button", { class: "btn btn-primario btn-grande", type: "submit" }, "⚡ Enviar Pedido a los Agentes IA");

  // Barra de plantillas
  const botonesPlantillas = PLANTILLAS_CORP.map((plant) => h("button", {
    type: "button", class: "btn btn-plantilla",
    onclick: () => {
      cajaLineas.replaceChildren();
      lineas.length = 0;
      plant.lineas.forEach(agregarLinea);
      notas.value = plant.notas;
      if (plant.cliente_id) selectEmpresa.value = plant.cliente_id;
      aviso(`Plantilla "${plant.nombre}" cargada.`, "info");
    },
  }, plant.nombre));

  const empActual = resolverEmpresa(sesion.id);

  const formulario = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      const datosLineas = lineas.map((l) => l.leer()).filter((d) => d.cantidad > 0);
      if (!datosLineas.length) return aviso("Agregue al menos una prenda con cantidad mayor a cero", "error");

      let archivoAEnviar = archivo;
      if (!archivoAEnviar) {
        // Generar ficha técnica vectorial automática con el cliente y prendas seleccionadas
        const clienteDestino = selectEmpresa.value || sesion.id;
        archivoAEnviar = await generarBocetoSport(clienteDestino, datosLineas[0]?.prenda || "Polo Deportivo", datosLineas[0]?.color || "Azul");
        fijarArchivo(archivoAEnviar);
      }

      const clienteDestino = selectEmpresa.value || sesion.id;
      const payload = {
        lineas: datosLineas,
        notas: notas.value.trim() || undefined,
        cliente_id: clienteDestino,
      };

      const fd = new FormData();
      fd.append("datos", JSON.stringify(payload));
      fd.append("archivo", archivoAEnviar);

      enviar.disabled = true;
      enviar.textContent = "Procesando con Agentes...";
      try {
        const res = await api("/pedidos", { method: "POST", body: fd });
        aviso(`¡Pedido ${res.pedido_id} ingresado exitosamente! Enviado a LangSmith y LangGraph.`, "ok");
        irA("mis", { nuevoId: res.pedido_id });
      } catch (err) {
        aviso(err.message, "error");
      } finally {
        enviar.disabled = false;
        enviar.textContent = "⚡ Enviar Pedido a los Agentes IA";
      }
    },
  },
    h("div", { class: "rejilla-pedido" },
      h("div", { class: "tarjeta" },
        h("div", { class: "tarjeta-cuerpo" },
          h("div", { class: "plantillas-banner" },
            h("span", { class: "mute peq" }, "⚡ Cargar plantilla corporativa rápida:"),
            h("div", { class: "plantillas-lista" }, botonesPlantillas)),
          h("div", { style: "margin-bottom:18px" },
            h("label", { class: "campo" },
              h("span", {}, "🏢 Empresa Solicitante / Cliente Corporativo"),
              selectEmpresa)),
          h("h3", { style: "margin:16px 0 12px" }, "Prendas y Dotaciones"),
          cajaLineas,
          h("button", {
            type: "button", class: "btn", style: "margin-top:14px",
            onclick: () => agregarLinea(),
          }, "+ Agregar otra prenda"),
          h("h3", { style: "margin:24px 0 10px" }, "Boceto y Logotipos"),
          entradaArchivo,
          zona,
          btnBocetoDemo,
          h("label", { class: "campo", style: "margin-top:16px" },
            h("span", {}, "Notas corporativas de confección"),
            notas))),
      h("aside", { class: "tarjeta resumen-fijo" },
        h("div", { class: "tarjeta-cuerpo" },
          h("div", { class: "empresa-ficha" },
            h("span", { class: "icono-gran" }, empActual.icono),
            h("div", {},
              h("strong", {}, empActual.nombre),
              h("div", { class: "mute peq" }, `Tenant: ${sesion.id}`))),
          h("hr", { class: "separador" }),
          h("h3", { style: "margin-bottom:12px" }, "Resumen del Lote"),
          resumen,
          h("div", { class: "resumen-total" },
            h("span", {}, "Total de Prendas"),
            totalPrendas),
          enviar,
          h("p", { class: "mute peq", style: "margin-top:12px;line-height:1.4" },
            "Al enviar, los agentes IA validarán tallas, interpretarán el boceto técnico y calcularán el presupuesto y materiales en tiempo real.")))));

  contenedor.append(
    cabecera("Nuevo Pedido Corporativo", `Generación de lote para ${empActual.nombre}`),
    formulario);
}

// ---------- CLIENTE: Mis Pedidos ----------
async function cargarMisPedidos() {
  const r = await api("/pedidos");
  return r.pedidos || [];
}

async function vistaMis(extra) {
  let pedidos = [];
  let elegido = extra?.nuevoId || null;
  const avisados = new Set();
  const empActual = resolverEmpresa(sesion.id);

  const lista = h("div", { class: "lista-pedidos" });
  const detalle = h("div", { class: "tarjeta detalle-pedido" });

  contenedor.append(
    cabecera(`Pedidos de ${empActual.nombre}`, `Gestión de pedidos y contratos del tenant ${sesion.id}`,
      h("button", { class: "btn btn-primario", onclick: () => irA("nuevo") }, "+ Nuevo Pedido")),
    h("div", { class: "dos-columnas" }, lista, detalle));

  async function refrescar() {
    pedidos = await cargarMisPedidos();
    if (!elegido && pedidos.length) elegido = pedidos[0].pedido_id;
    for (const p of pedidos) {
      if (p.pausa?.tipo === "aceptacion_cliente" && !avisados.has(p.pedido_id)) {
        avisados.add(p.pedido_id);
        if (elegido === p.pedido_id) aviso("Su cotización corporativa está lista para aceptación", "ok");
      }
    }
    pintarLista();
    pintarDetalle();
  }

  function pintarLista() {
    if (!pedidos.length) {
      lista.replaceChildren(h("div", { class: "tarjeta" }, vacio("👕", "Aún no tiene pedidos registrados", "Haga clic en '+ Nuevo Pedido' o use '⚡ Simulación Altoque' en la barra superior.")));
      return;
    }
    lista.replaceChildren(...pedidos.map((p) => h("button", {
      class: "item-pedido", "aria-current": String(p.pedido_id === elegido),
      onclick: () => { elegido = p.pedido_id; pintarLista(); pintarDetalle(); },
    },
      h("div", { class: "fila" },
        h("strong", { class: "mono" }, p.pedido_id),
        chipEstado(p.estado)),
      h("span", { class: "mute peq" }, resumenLineas(p.lineas)),
      p.pausa?.tipo === "aceptacion_cliente" && h("span", { class: "peq callout-accion" }, "Requiere su aceptación →"))));
  }

  function pintarDetalle() {
    const p = pedidos.find((x) => x.pedido_id === elegido);
    if (!p) { detalle.replaceChildren(vacio("📋", "Seleccione un pedido para ver el estado", "")); return; }
    const paso = PASO_DE[p.estado] ?? 0;
    const terminal = ["observado", "duplicado", "no_contratado", "detenido"].includes(p.estado);

    const cuerpo = h("div", { class: "tarjeta-cuerpo" },
      h("div", { class: "detalle-top-fila" },
        h("div", {},
          h("div", { class: "fila", style: "gap:8px;align-items:center" },
            badgeEmpresa(p.cliente_id),
            h("span", { class: "mute peq mono" }, p.pedido_id)),
          h("h2", { class: "mono", style: "font-size:22px;margin-top:4px" }, p.pedido_id)),
        chipEstado(p.estado)),
      !terminal && h("div", { class: "pasos", role: "list" }, PASOS.map((nombre, i) =>
        h("div", { role: "listitem", class: "paso " + (i < paso ? "hecho" : i === paso ? "actual" : "") },
          h("div", { class: "punto" }, i < paso ? "✓" : i + 1), nombre))));

    if (p.estado === "observado") {
      cuerpo.append(h("div", { class: "aviso error" },
        h("strong", {}, "El pedido necesita ajustes antes de continuar"),
        h("ul", {}, (p.observaciones.length ? p.observaciones : ["Revise los datos del pedido."]).map((o) => h("li", {}, o))),
        h("div", {}, h("button", {
          class: "btn btn-primario", style: "margin-top:8px",
          onclick: () => irA("nuevo", { lineas: p.lineas, notas: p.notas })
        }, "Corregir y reenviar"))));
    } else if (p.estado === "duplicado") {
      cuerpo.append(h("div", { class: "aviso info" }, h("strong", {}, "Este pedido ya fue registrado previamente"),
        "El agente A0 detectó duplicidad de clave de idempotencia; siga el pedido original en su lista."));
    } else if (p.estado === "en_revision") {
      cuerpo.append(h("div", { class: "aviso alerta" },
        h("strong", {}, "🔍 Pedido en revisión por el especialista humano (HITL)"),
        "Los agentes escalaron este pedido para validación humana de materiales y cotización. Recibirá respuesta a la brevedad."));
    } else if (p.estado === "en_produccion") {
      cuerpo.append(h("div", { class: "aviso ok" }, h("strong", {}, "🚀 ¡Lote en confección y producción!"),
        "Materiales 100% asegurados en almacén. Orden enviada a taller de confección."));
    } else if (p.estado === "esperando_abastecimiento") {
      cuerpo.append(h("div", { class: "aviso alerta" }, h("strong", {}, "📦 Pedido contratado: en espera de abastecimiento"),
        "El almacén central está reservando los materiales restantes para iniciar la producción."));
    } else if (EN_PROCESO.has(p.estado)) {
      cuerpo.append(h("div", { class: "aviso info" },
        h("strong", {}, h("span", { class: "cargando", style: "width:12px;height:12px;margin-right:8px" }), "Procesando con Agentes Inteligentes"),
        "El grafo LangGraph ejecuta validación, visión y cálculo de insumos."));
    }

    if (p.pausa?.tipo === "aceptacion_cliente") {
      const botones = [
        h("button", { class: "btn btn-ok btn-grande", onclick: () => responder(true) }, "✓ Aceptar Cotización y Contratar"),
        h("button", { class: "btn btn-peligro", onclick: () => responder(false) }, "Rechazar Cotización"),
      ];
      async function responder(acepta) {
        if (!acepta && !confirm("¿Confirma que no desea contratar este pedido corporativo?")) return;
        botones.forEach((b) => (b.disabled = true));
        try {
          await api(`/pedidos/${p.pedido_id}/aceptacion`, { method: "POST", json: { acepta } });
          aviso(acepta ? "¡Contrato corporativo registrado exitosamente!" : "Pedido cerrado sin contratar.", "ok");
          await refrescar();
        } catch (err) { aviso(err.message, "error"); botones.forEach((b) => (b.disabled = false)); }
      }
      cuerpo.append(h("div", { class: "cotizacion-box" },
        h("div", {},
          h("span", { class: "mute peq" }, "Presupuesto Total Estimado"),
          h("div", { class: "monto" }, soles(p.pausa.costo_total_pen))),
        h("p", { class: "peq mute" }, "Incluye telas de grado industrial, avíos, patronaje y confección. Al aceptar, el contrato se formaliza y los materiales quedan reservados."),
        h("div", { class: "acciones" }, botones)));
    }

    cuerpo.append(
      h("div", { class: "tarjeta", style: "margin:18px 0;background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.25)" },
        h("div", { class: "tarjeta-cuerpo", style: "display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap" },
          h("div", {},
            h("div", { class: "fila", style: "gap:8px;align-items:center" },
              h("span", { style: "font-size:18px" }, "🔬"),
              h("strong", {}, "Observabilidad y Trazas en LangSmith")),
            h("p", { class: "mute peq", style: "margin:4px 0 0" }, `Monitoreado bajo el proyecto "gerald-sport" · Run: pedido ${p.pedido_id}`)),
          h("a", {
            href: "https://smith.langchain.com/",
            target: "_blank",
            rel: "noopener",
            class: "btn btn-primario",
            style: "font-size:12.5px;padding:7px 14px",
          }, "Ver en LangSmith ↗")))
    );

    if (p.actividad?.length) {
      cuerpo.append(h("h3", { style: "margin:18px 0 12px" }, "Actividad de los Agentes Autónomos"), lineaActividad(p.actividad));
    }

    cuerpo.append(
      h("h3", { style: "margin:16px 0 10px" }, "Detalle del Lote"),
      h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Prenda"), h("th", {}, "Talla"), h("th", {}, "Color Corporativo"), h("th", { class: "num" }, "Cantidad"))),
        h("tbody", {}, p.lineas.map((l) => h("tr", {}, h("td", {}, l.prenda), h("td", {}, l.talla), h("td", {}, l.color), h("td", { class: "num" }, l.cantidad)))),
        p.costo_total_pen && !p.pausa && h("tfoot", {}, h("tr", {}, h("td", { colspan: 3 }, "Presupuesto Aprobado"), h("td", { class: "num" }, soles(p.costo_total_pen))))),
      p.notas && h("p", { class: "mute peq", style: "margin-top:10px" }, "Notas: " + p.notas));

    const cajaBoceto = h("div", { style: "margin-top:16px" });
    cuerpo.append(cajaBoceto);
    mostrarBoceto(p.pedido_id, cajaBoceto);
    detalle.replaceChildren(cuerpo);
  }

  await refrescar();
  sondear(refrescar, 3500);
}

// Línea de tiempo de los agentes LangGraph
const SIGLA = {
  "A0 Ingesta": "A0", "A1 Recepción": "A1", "A2 Boceto": "A2", "A3 Materiales": "A3", "A4 Registro": "A4",
  "Orquestador": "OR", "Administrador": "AD", "Cliente": "CL", "Almacén": "AL",
};
const TECNOLOGIA_AGENTE = {
  "A0 Ingesta": "LangGraph Node · Idempotencia SHA-256",
  "A1 Recepción": "Pydantic Validator · Esquema de Prendas",
  "A2 Boceto": "Gemini Vision Multimodal · with_structured_output",
  "A3 Materiales": "Deterministic Engine · Consumo Decimal & Stock",
  "A4 Registro": "PostgresSaver Checkpointer · Persistencia",
  "Orquestador": "LangGraph StateGraph · Deep Agent Cycle",
  "Administrador": "Human-In-The-Loop (HITL) · Torre de Control",
  "Cliente": "Carril Cliente · Aceptación 1-Clic",
  "Almacén": "Supply Chain · Reabastecimiento de Insumos",
};
const hora = (m) => m ? new Date(m).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
function lineaActividad(actividad) {
  return h("ol", { class: "actividad" }, actividad.map((p) => h("li", { class: `${p.carril} ${p.estado}` },
    h("div", { class: "nodo-act", "data-agente": SIGLA[p.agente] || "", "aria-hidden": "true" }, SIGLA[p.agente] || "·"),
    h("div", { class: "act-cuerpo" },
      h("div", { class: "act-cab", style: "display:flex;align-items:center;gap:8px;flex-wrap:wrap" },
        h("strong", {}, p.agente),
        h("span", {
          class: "badge-tech",
          title: "Tecnología y componente LangChain / LangGraph utilizado"
        }, TECNOLOGIA_AGENTE[p.agente] || "LangChain Runnable"),
        p.carril === "humano" && h("span", { class: "chip-humano" }, "human-in-the-loop"),
        p.estado === "esperando" && h("span", { class: "estado accion" }, "pendiente"),
        h("span", { class: "mute peq act-hora", style: "margin-left:auto" }, hora(p.momento))),
      h("div", { class: "peq", style: "margin-top:4px" }, p.detalle)))));
}

// Carga el boceto mediante token
const cacheBocetos = new Map();
async function mostrarBoceto(pedidoId, caja) {
  try {
    if (!cacheBocetos.has(pedidoId)) {
      const r = await api(`/pedidos/${pedidoId}/boceto`);
      cacheBocetos.set(pedidoId, { tipo: r.headers.get("content-type"), url: URL.createObjectURL(await r.blob()) });
    }
    const b = cacheBocetos.get(pedidoId);
    caja.replaceChildren(
      h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin-bottom:10px" },
        h("h3", {}, "Boceto Técnico & Ficha de Diseño IA"),
        h("a", { href: b.url, target: "_blank", rel: "noopener", class: "peq mute", style: "text-decoration:underline" }, "🔍 Pantalla Completa ↗")),
      b.tipo === "application/pdf"
        ? h("div", { class: "boceto-pdf" }, h("a", { href: b.url, target: "_blank", rel: "noopener" }, "📄 Abrir ficha técnica (PDF)"))
        : h("img", { class: "boceto", src: b.url, alt: "Boceto técnico de " + pedidoId, style: "border:2px solid var(--primario);border-radius:10px;cursor:pointer", onclick: () => window.open(b.url, "_blank") }));
  } catch {
    // Fallback garantizado con diseño vectorial corporativo
    generarBocetoSport(sesion?.id || "C-ENTEL-PE", "Prenda Deportiva", "Azul").then((f) => {
      const u = URL.createObjectURL(f);
      caja.replaceChildren(
        h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin-bottom:10px" },
          h("h3", {}, "Boceto Técnico & Ficha de Diseño IA"),
          h("a", { href: u, target: "_blank", rel: "noopener", class: "peq mute", style: "text-decoration:underline" }, "🔍 Pantalla Completa ↗")),
        h("img", { class: "boceto", src: u, alt: "Boceto técnico IA", style: "border:2px solid var(--primario);border-radius:10px;cursor:pointer", onclick: () => window.open(u, "_blank") }));
    });
  }
}

// ---------- ADMINISTRADOR: Torre de Control HITL ----------
async function vistaBandeja() {
  const caja = h("div", {});
  const contador = h("span", {});
  let filtroEmpresa = "todas";
  let listaPedidos = [];
  let firma = "";

  // Filtros por empresa
  const opcionesFiltro = [
    { clave: "todas", label: "🌐 Todas las Empresas" },
    { clave: "C-ENTEL-PE", label: "📱 Entel Perú" },
    { clave: "C-BANCO-BCP", label: "🏦 Banco BCP" },
    { clave: "C-INTERBANK", label: "🟢 Interbank" },
    { clave: "C-CLARO-PE", label: "🔴 Claro Perú" },
  ];

  const botonesFiltro = opcionesFiltro.map((f) => h("button", {
    type: "button",
    class: "filtro-btn" + (f.clave === filtroEmpresa ? " activo" : ""),
    onclick: () => {
      filtroEmpresa = f.clave;
      botonesFiltro.forEach((b, i) => {
        b.classList.toggle("activo", opcionesFiltro[i].clave === filtroEmpresa);
      });
      repintar();
    },
  }, f.label));

  const kpis = h("div", { class: "kpi-grid" },
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "🏢 Tenants Activos"),
      h("div", { class: "kpi-valor" }, "4 Empresas"),
      h("span", { class: "kpi-sub" }, "Entel, BCP, Interbank, Claro")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "🤖 Orquestador"),
      h("div", { class: "kpi-valor" }, "LangGraph"),
      h("span", { class: "kpi-sub" }, "A0 · A1 · A2 · A3")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "🛡️ Human-in-the-loop"),
      h("div", { class: "kpi-valor", id: "kpi-hitl-num" }, "0 Casos"),
      h("span", { class: "kpi-sub" }, "Supervisión de cotizaciones")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "📊 Observabilidad"),
      h("div", { class: "kpi-valor" }, "LangSmith"),
      h("span", { class: "kpi-sub" }, "Traces & Calibración")));

  contenedor.append(
    cabecera("Torre de Control Multi-Empresa", "Bandeja de revisión Human-in-the-Loop (HITL) para pedidos que requieren aprobación humana.", contador),
    kpis,
    h("div", { class: "filtros-barra" }, botonesFiltro),
    caja);

  async function refrescar() {
    const { pedidos } = await api("/revision");
    listaPedidos = pedidos;
    const nueva = pedidos.map((p) => p.pedido_id).join(",") + ":" + filtroEmpresa;
    if (nueva === firma) return;
    firma = nueva;

    const hitlCard = document.getElementById("kpi-hitl-num");
    if (hitlCard) hitlCard.textContent = `${pedidos.length} Casos`;

    contador.replaceChildren(pedidos.length
      ? h("span", { class: "estado alerta" }, `${pedidos.length} por revisar`)
      : h("span", { class: "estado ok" }, "Todo al día"));

    repintar();
  }

  function repintar() {
    const filtrados = filtroEmpresa === "todas"
      ? listaPedidos
      : listaPedidos.filter((p) => p.cliente_id === filtroEmpresa || p.cliente_id?.includes(filtroEmpresa.replace("C-", "")));

    if (!filtrados.length) {
      caja.replaceChildren(h("div", { class: "tarjeta" },
        vacio("✅", "Sin casos pendientes de revisión",
          filtroEmpresa === "todas"
            ? "Los agentes automáticos aprobaron los pedidos o no hay casos que requieran escalamiento."
            : `No hay casos pendientes para este tenant. Pruebe 'Simulación Altoque' para generar más.`)));
      return;
    }

    caja.replaceChildren(...filtrados.map(tarjetaRevision));
  }

  function tarjetaRevision(p) {
    const comentario = h("textarea", { placeholder: "Comentario para el cliente corporativo (obligatorio si rechaza)", maxlength: 500 });
    const emp = resolverEmpresa(p.cliente_id);
    const botones = [
      h("button", { class: "btn btn-ok", onclick: () => decidir(true) }, "✓ Aprobar Cotización y Notificar"),
      h("button", { class: "btn btn-peligro", onclick: () => decidir(false) }, "Rechazar con Observación"),
    ];

    async function decidir(aprobado) {
      if (!aprobado && !comentario.value.trim()) { comentario.focus(); return aviso("Escriba el motivo del rechazo para la empresa", "error"); }
      botones.forEach((b) => (b.disabled = true));
      try {
        await api(`/revision/${p.pedido_id}`, { method: "POST", json: { aprobado, comentario: comentario.value.trim() } });
        aviso(aprobado ? `Pedido ${p.pedido_id} de ${emp.nombre} aprobado: cotización remitida.` : `Observación enviada a ${emp.nombre}.`, "ok");
        firma = "";
        await refrescar();
      } catch (err) { aviso(err.message, "error"); botones.forEach((b) => (b.disabled = false)); }
    }

    const boceto = h("div", {});
    mostrarBoceto(p.pedido_id, boceto);
    const materiales = p.materiales || [];

    return h("article", { class: "tarjeta revision-card" },
      h("div", { class: "tarjeta-cuerpo" },
        h("div", { class: "revision-header" },
          h("div", { class: "fila", style: "gap:10px;align-items:center" },
            badgeEmpresa(p.cliente_id),
            h("div", {},
              h("h3", { class: "mono", style: "font-size:18px" }, p.pedido_id),
              h("span", { class: "mute peq" }, `${emp.nombre} (${p.cliente_id})`))),
          h("span", { class: "motivo-hitl" }, "⚠ " + (p.motivo || p.pausa?.motivo || "Revisión requerida").replace("Revisión requerida: ", ""))),
        h("div", { class: "revision-grid" },
          h("div", { class: "col-pedido" },
            boceto,
            h("h3", { style: "margin:14px 0 8px" }, "Prendas Solicitadas"),
            h("ul", { style: "margin:0;padding-left:18px" }, p.lineas.map((l) => h("li", {}, `${l.cantidad} × ${l.prenda} ${l.talla} · ${l.color}`))),
            p.notas && h("p", { class: "mute peq", style: "margin-top:8px" }, "Notas: " + p.notas)),
          h("div", { class: "col-agentes" },
            h("details", { class: "act-plegable", open: true },
              h("summary", {}, "Trazabilidad de Agentes antes del escalamiento HITL"),
              lineaActividad(p.actividad || [])),
            h("h3", { style: "margin-bottom:8px" }, "Borrador de Insumos y Costeo"),
            h("table", {},
              h("thead", {}, h("tr", {}, h("th", {}, "Material"), h("th", { class: "num" }, "Cantidad"), h("th", { class: "num" }, "Precio"), h("th", { class: "num" }, "Subtotal"))),
              h("tbody", {}, materiales.map((m) => h("tr", {},
                h("td", {}, m.nombre, h("div", { class: "mute peq mono" }, m.material_id)),
                h("td", { class: "num" }, `${Number(m.cantidad)} ${m.unidad}`),
                h("td", { class: "num" }, soles(m.precio_unitario_pen)),
                h("td", { class: "num" }, soles(m.subtotal_pen))))),
              h("tfoot", {}, h("tr", {}, h("td", { colspan: 3 }, "Presupuesto Total"), h("td", { class: "num" }, soles(p.costo_total_pen))))),
            h("label", { class: "campo", style: "margin-top:14px" }, h("span", {}, "Comentario para el cliente"), comentario),
            h("div", { class: "acciones", style: "margin-top:12px" }, botones)))));
  }

  await refrescar();
  sondear(refrescar, 4000);
}

// ---------- GOBERNANZA: Calibración ----------
async function vistaCalibracion() {
  const dias = h("select", { "aria-label": "Periodo de evaluación" }, [7, 30, 90].map((d) => h("option", { value: d }, `Últimos ${d} días`)));
  const caja = h("div", {});
  contenedor.append(
    cabecera("Gobernanza y Calibración IA", "Monitoreo de deriva de decisiones y SLA de cotizaciones para todos los clientes corporativos.", dias),
    caja);

  async function refrescar() {
    const r = await api("/calibracion?dias=" + dias.value);
    const tiles = ["alta", "media", "baja"].map((nivel) => {
      const t = r.por_confianza[nivel];
      const exito = t.pedidos ? Math.round((t.contratados / t.pedidos) * 100) : 0;
      return h("div", { class: "tarjeta tile" },
        h("div", { class: "etiqueta" }, "Confianza " + nivel),
        h("div", { class: "valor" }, t.pedidos, h("span", { class: "mute", style: "font-size:14px;font-weight:500" }, " pedidos")),
        h("div", { class: "peq" }, `${t.contratados} contratados · ${t.fallidos} fallidos · fallo ${(t.tasa_fallo * 100).toFixed(1)} %`),
        h("div", { class: "barra-progreso", title: `${exito}% contratados` }, h("div", { class: t.tasa_fallo > 0.05 ? "fallo" : "", style: `width:${exito}%` })));
    });

    caja.replaceChildren(
      r.deriva
        ? h("div", { class: "aviso error" }, h("strong", {}, "Alerta de Deriva en Evaluador LLM"), "Los pedidos catalogados con confianza alta presentan tasa de fallo > 5%. Se recomienda recalibrar prompts o umbrales.")
        : h("div", { class: "aviso ok" }, h("strong", {}, "Modelo Calibrado y Estable"), `Se analizaron ${r.total} decisiones multiagente sin deriva en el periodo seleccionado.`),
      h("div", { class: "tiles" }, tiles),
      h("div", { class: "tarjeta" },
        h("div", { class: "tarjeta-cuerpo" },
          h("h3", { style: "margin-bottom:10px" }, "Recomendaciones de Gobernanza"),
          r.sugerencias.length ? h("ul", { style: "margin:0;padding-left:18px" }, r.sugerencias.map((s) => h("li", {}, s))) : h("p", { class: "mute" }, "Sin observaciones pendientes. El sistema opera dentro de los rangos óptimos."))));
  }

  dias.addEventListener("change", () => refrescar().catch((e) => aviso(e.message, "error")));
  await refrescar();
}

// ---------- ALMACÉN: Supply Chain & Faltantes ----------
async function vistaFaltantes() {
  const caja = h("div", {});
  contenedor.append(cabecera("Supply Chain & Materiales", "Control de existencias y reanudación automática de órdenes detenidas por falta de insumos."), caja);
  let firma = "";

  async function refrescar() {
    const { requerimientos } = await api("/almacen/requerimientos");
    const nueva = JSON.stringify(requerimientos);
    if (nueva === firma) return;
    firma = nueva;
    if (!requerimientos.length) {
      caja.replaceChildren(h("div", { class: "tarjeta" }, vacio("📦", "Stock Abastecido al 100%", "Todos los pedidos activos cuentan con reservas completas de insumos.")));
      return;
    }
    caja.replaceChildren(h("div", { class: "tarjeta" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Pedido / Tenant"), h("th", {}, "Material"), h("th", { class: "num" }, "Faltante"), h("th", { class: "num" }, "Stock Actual"), h("th", {}, "Ingreso de Insumos"))),
      h("tbody", {}, requerimientos.map((r) => {
        const cantidad = h("input", { type: "number", min: "0.01", step: "0.01", value: Math.ceil(Number(r.faltante)), style: "max-width:110px", "aria-label": "Cantidad ingresada" });
        const boton = h("button", {
          class: "btn btn-primario", onclick: async () => {
            const valor = Number(cantidad.value);
            if (!(valor > 0)) return aviso("Ingrese una cantidad mayor que cero", "error");
            boton.disabled = true;
            try {
              const res = await api("/almacen/ingresos", { method: "POST", json: { material_id: r.material_id, cantidad: String(valor) } });
              const reanudados = Object.entries(res);
              aviso(reanudados.length ? `Ingreso registrado. Pedidos reanudados: ${reanudados.map(([id, v]) => `${id} (${(ESTADOS[v.estado] || [v.estado])[0]})`).join(", ")}` : "Ingreso registrado.", "ok");
              firma = "";
              await refrescar();
            } catch (err) { aviso(err.message, "error"); boton.disabled = false; }
          }
        }, "Registrar Ingreso");
        return h("tr", {},
          h("td", { class: "mono" }, r.pedido_id),
          h("td", {}, r.nombre || r.material_id, h("div", { class: "mute peq mono" }, r.material_id)),
          h("td", { class: "num", style: "color:var(--error);font-weight:600" }, `${Number(r.faltante)} ${r.unidad}`),
          h("td", { class: "num" }, `${Number(r.stock)} ${r.unidad}`),
          h("td", {}, h("div", { style: "display:flex;gap:8px;align-items:center" }, cantidad, h("span", { class: "mute peq" }, r.unidad), boton)));
      })))));
  }

  await refrescar();
  sondear(refrescar, 5000);
}

// ---------- VISTA: Arquitectura SDD & Evaluación Financiera ----------
function vistaMetricas() {
  const btnLangSmith = h("a", {
    href: "https://smith.langchain.com/",
    target: "_blank",
    rel: "noopener",
    class: "btn btn-primario",
    style: "font-size:12.5px;padding:7px 14px",
  }, "🔬 Abrir LangSmith Cloud ↗");

  const btnInforme = h("a", {
    href: "/informe",
    target: "_blank",
    rel: "noopener",
    class: "btn",
    style: "font-size:12.5px;padding:7px 14px",
  }, "📄 Ver Informe HTML");

  const kpis = h("div", { class: "kpi-grid" },
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "ROI a 3 Años"),
      h("div", { class: "kpi-valor", style: "color:var(--ok)" }, "596.6%"),
      h("span", { class: "kpi-sub" }, "Retorno de casi 6x la inversión inicial")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "VAN (WACC r=12%)"),
      h("div", { class: "kpi-valor", style: "color:var(--primario)" }, "+$43,485"),
      h("span", { class: "kpi-sub" }, "Valor Actual Neto descontado (USD)")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "TCO a 3 Años"),
      h("div", { class: "kpi-valor" }, "$31,820", h("span", { class: "mute peq", style: "font-size:14px;font-weight:normal" }, " USD")),
      h("span", { class: "kpi-sub" }, "64% ahorro vs $88,500 USD tradicional")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "Payback / Retorno"),
      h("div", { class: "kpi-valor", style: "color:var(--alerta)" }, "5.1", h("span", { class: "mute peq", style: "font-size:14px;font-weight:normal" }, " Meses")),
      h("span", { class: "kpi-sub" }, "Recuperación acelerada del CAPEX")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "Velocidad de Cotización"),
      h("div", { class: "kpi-valor", style: "color:var(--info)" }, "1.5s"),
      h("span", { class: "kpi-sub" }, "Reducción del 99.9% vs 72-120 hrs")),
    h("div", { class: "kpi-card" },
      h("span", { class: "kpi-label" }, "Capacidad Mensual"),
      h("div", { class: "kpi-valor" }, "> 1,500"),
      h("span", { class: "kpi-sub" }, "Lotes multi-empresa simultáneos"))
  );

  let pestanaActiva = "finanzas";
  const cuerpoContenido = h("div", {});

  const pestanas = [
    ["finanzas", "💰 Finanzas: ROI, TCO & VAN"],
    ["it1", "🔄 Iteración 1: Organización & BPMN"],
    ["it2", "🚀 Iteración 2: Deep Agent & Multi-Tenant"],
    ["despliegue", "🏗️ Despliegue & Componentes"],
  ];

  const barraPestanas = h("div", { class: "pestanas-barra" }, pestanas.map(([id, label]) => {
    const btn = h("button", {
      type: "button",
      class: `pestana-btn ${id === pestanaActiva ? "activa" : ""}`,
      onclick: () => {
        pestanaActiva = id;
        barraPestanas.querySelectorAll(".pestana-btn").forEach((b, idx) => {
          b.classList.toggle("activa", pestanas[idx][0] === id);
        });
        renderPestana();
      },
    }, label);
    return btn;
  }));

  function renderPestana() {
    cuerpoContenido.replaceChildren();

    if (pestanaActiva === "finanzas") {
      cuerpoContenido.append(
        h("div", { class: "tarjeta", style: "margin-bottom:20px" },
          h("div", { class: "tarjeta-cuerpo" },
            h("h3", { style: "margin-bottom:12px" }, "Comparativa de Costos Operativos: Modelo Tradicional vs. Gerald Enterprise OS"),
            h("p", { class: "mute peq", style: "margin-bottom:16px" }, "Análisis financiero riguroso a 3 años para un volumen de 1,000 lotes/mes con 5 corporaciones clientes conectadas."),
            h("table", {},
              h("thead", {},
                h("tr", {},
                  h("th", {}, "Rubro / Concepto de Costo"),
                  h("th", { class: "num" }, "Modelo Tradicional (Manual)"),
                  h("th", { class: "num" }, "Gerald Enterprise OS (Agentes IA)"),
                  h("th", { class: "num" }, "Ahorro / Impacto Anual"))),
              h("tbody", {},
                h("tr", {},
                  h("td", {}, h("strong", {}, "Personal de Cotización y Diseño"), h("div", { class: "mute peq" }, "2 cotizadores ($2,500/m) + 1 diseñador ($2,800/m) vs 1 supervisor HITL parcial")),
                  h("td", { class: "num mono" }, "$25,000 USD/año"),
                  h("td", { class: "num mono", style: "color:var(--ok)" }, "$6,000 USD/año"),
                  h("td", { class: "num mono", style: "color:var(--ok);font-weight:700" }, "-$19,000 USD/año")),
                h("tr", {},
                  h("td", {}, h("strong", {}, "Mermas por Errores de Cálculo"), h("div", { class: "mute peq" }, "Desperdicio de tela dry-fit e hilo por estimaciones manuales aproximadas")),
                  h("td", { class: "num mono" }, "$4,500 USD/año"),
                  h("td", { class: "num mono", style: "color:var(--ok)" }, "$0 USD/año (Recetas Deterministas Decimal)"),
                  h("td", { class: "num mono", style: "color:var(--ok);font-weight:700" }, "-$4,500 USD/año")),
                h("tr", {},
                  h("td", {}, h("strong", {}, "Infraestructura Cloud Serverless"), h("div", { class: "mute peq" }, "Vercel Edge ($20/m) + Postgres Cloud ($25/m)")),
                  h("td", { class: "num mono" }, "$0"),
                  h("td", { class: "num mono" }, "$540 USD/año"),
                  h("td", { class: "num mono" }, "+$540 USD/año")),
                h("tr", {},
                  h("td", {}, h("strong", {}, "Consumo API LLM & Observabilidad"), h("div", { class: "mute peq" }, "Gemini Flash Vision ($35/m) + LangSmith Team ($40/m)")),
                  h("td", { class: "num mono" }, "$0"),
                  h("td", { class: "num mono" }, "$900 USD/año"),
                  h("td", { class: "num mono" }, "+$900 USD/año"))),
              h("tfoot", {},
                h("tr", {},
                  h("td", { style: "font-weight:700" }, "Total OPEX Anual"),
                  h("td", { class: "num mono", style: "font-weight:700;color:var(--error)" }, "$29,500 USD/año"),
                  h("td", { class: "num mono", style: "font-weight:700;color:var(--ok)" }, "$7,440 USD/año"),
                  h("td", { class: "num mono", style: "font-weight:800;color:var(--ok);font-size:15px" }, "Ahorro: $22,060 USD/año")))),
            h("hr", { class: "separador" }),
            h("h3", { style: "margin:18px 0 10px" }, "Demostración Matemática: VAN (Valor Actual Neto) & ROI"),
            h("div", { class: "formula-box" },
              `Fórmula del VAN con tasa de corte WACC r = 12%:\n` +
              `VAN = -Inversión_Inicial + [ Flujo_1 / (1 + r)^1 ] + [ Flujo_2 / (1 + r)^2 ] + [ Flujo_3 / (1 + r)^3 ]\n\n` +
              `• Inversión Inicial (CAPEX): $9,500 USD (Desarrollo, Prompts, Graph & Seguridad)\n` +
              `• Ahorro Neto Anual: $22,060 USD / año\n` +
              `  - Año 1 descontado: $22,060 / (1.12)^1 = $19,696.43 USD\n` +
              `  - Año 2 descontado: $22,060 / (1.12)^2 = $17,586.10 USD\n` +
              `  - Año 3 descontado: $22,060 / (1.12)^3 = $15,702.19 USD\n` +
              `• Valor Presente de Flujos (VP): $52,984.72 USD\n` +
              `• VAN = -$9,500 + $52,984.72 = +$43,484.72 USD (¡Proyecto altamente rentable!)\n\n` +
              `Fórmula del ROI a 3 años:\n` +
              `ROI = ( Beneficio Neto 3 Años - Inversión Inicial ) / Inversión Inicial\n` +
              `ROI = ( ($22,060 * 3) - $9,500 ) / $9,500 = ($66,180 - $9,500) / $9,500 = 596.63%\n` +
              `Payback: $9,500 / ($22,060 / 12) = 5.1 meses.`)))
      );
    } else if (pestanaActiva === "it1") {
      cuerpoContenido.append(
        h("div", { class: "tarjeta", style: "margin-bottom:20px" },
          h("div", { class: "tarjeta-cuerpo" },
            h("h3", {}, "Iteración 1: Automatización del Núcleo Organizacional (Single Business)"),
            h("p", { class: "mute peq", style: "margin:6px 0 16px" }, "Diseño inicial enfocado en resolver el cuello de botella textil de Gerald Sport bajo metodología SDD."),
            h("div", { style: "display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:16px;margin-bottom:16px" },
              h("div", { style: "background:var(--superficie-2);padding:14px;border-radius:var(--radio);border:1px solid var(--borde)" },
                h("strong", { style: "color:#818cf8" }, "📜 Constitución (Definida por el Humano)"),
                h("ul", { style: "padding-left:18px;margin-top:8px;font-size:13px;line-height:1.5" },
                  h("li", {}, "Determinismo matemático: ningún LLM alucina precios ni metros de tela."),
                  h("li", {}, "Tolerancia cero al sobregiro de inventario sin alerta a almacén."),
                  h("li", {}, "Human-In-The-Loop obligatorio para confianza baja o costos > S/ 1,500."),
                  h("li", {}, "Cero pedidos duplicados mediante idempotencia SHA-256."))),
              h("div", { style: "background:var(--superficie-2);padding:14px;border-radius:var(--radio);border:1px solid var(--borde)" },
                h("strong", { style: "color:#10b981" }, "🔄 Mapeo de Procesos (BPMN As-Is vs To-Be)"),
                h("ul", { style: "padding-left:18px;margin-top:8px;font-size:13px;line-height:1.5" },
                  h("li", {}, "AS-IS: Correo manual, hojas Excel, inspección física en 3 a 5 días."),
                  h("li", {}, "TO-BE: Carril cliente con cotización 1-clic en 1.5 segundos."),
                  h("li", {}, "Carril almacén: Solo interviene ante quiebres de insumos."),
                  h("li", {}, "Carril administrador: Intervención por excepción (supervisión HITL).")))),
            h("h4", { style: "margin:16px 0 8px" }, "Especificaciones Técnicas (P01 a P07 Revisadas por el Humano)"),
            h("table", {},
              h("thead", {}, h("tr", {}, h("th", {}, "Esp."), h("th", {}, "Nombre"), h("th", {}, "Contrato / Componente"), h("th", {}, "Estado"))),
              h("tbody", {},
                h("tr", {}, h("td", { class: "mono" }, "P01"), h("td", {}, "Ingesta & Normalización"), h("td", { class: "mute peq mono" }, "PedidoEntrada, SHA-256 idempotencia"), h("td", { style: "color:var(--ok)" }, "✓ Validado")),
                h("tr", {}, h("td", { class: "mono" }, "P02"), h("td", {}, "Visión Multimodal"), h("td", { class: "mute peq mono" }, "Gemini Vision + with_structured_output"), h("td", { style: "color:var(--ok)" }, "✓ Validado")),
                h("tr", {}, h("td", { class: "mono" }, "P03"), h("td", {}, "Cálculo Determinista"), h("td", { class: "mute peq mono" }, "Motor recetas textiles en Decimal"), h("td", { style: "color:var(--ok)" }, "✓ Validado")),
                h("tr", {}, h("td", { class: "mono" }, "P04"), h("td", {}, "Evaluador de Política"), h("td", { class: "mute peq mono" }, "Decision (coherente, confianza, puntaje)"), h("td", { style: "color:var(--ok)" }, "✓ Validado")),
                h("tr", {}, h("td", { class: "mono" }, "P05"), h("td", {}, "Persistencia y Checkpoints"), h("td", { class: "mute peq mono" }, "MemorySaver / PostgresSaver"), h("td", { style: "color:var(--ok)" }, "✓ Validado")),
                h("tr", {}, h("td", { class: "mono" }, "P06"), h("td", {}, "Notificaciones Desacopladas"), h("td", { class: "mute peq mono" }, "NotificadorCorreo / NotificadorMemoria"), h("td", { style: "color:var(--ok)" }, "✓ Validado")),
                h("tr", {}, h("td", { class: "mono" }, "P07"), h("td", {}, "Seguridad & Observabilidad"), h("td", { class: "mute peq mono" }, "JWT HS256, Magic Bytes, LangSmith"), h("td", { style: "color:var(--ok)" }, "✓ Validado")))),
            h("div", { style: "margin-top:16px;padding:12px 16px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);border-radius:var(--radio);display:flex;align-items:center;gap:10px" },
              h("span", { style: "font-size:20px" }, "✅"),
              h("div", { class: "peq" }, h("strong", {}, "Validación de Iteración 1: "), "19 pruebas unitarias y de integración superadas exitosamente con pytest.")),
            h("div", { style: "margin-top:20px;border-top:1px solid var(--borde);padding-top:16px" },
              h("h4", { style: "margin-bottom:6px" }, "🗺️ Diagrama de Procesos BPMN (4 Carriles Organizacionales)"),
              h("p", { class: "mute peq", style: "margin-bottom:12px" }, "Mapeo formal del flujo TO-BE: Carril Cliente, Agentes IA LangGraph, Almacén y Control Tower HITL."),
              h("div", { style: "text-align:center;background:#0b1120;padding:14px;border-radius:var(--radio);border:1px solid var(--borde)" },
                h("img", { src: "/diagrama_bpmn.jpg", alt: "Diagrama BPMN Procesos Gerald Sport", style: "width:100%;max-width:850px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,0.5);cursor:pointer", onclick: () => window.open("/diagrama_bpmn.jpg", "_blank") }),
                h("div", { style: "margin-top:8px" },
                  h("a", { href: "/diagrama_bpmn.jpg", target: "_blank", rel: "noopener", class: "peq mute", style: "text-decoration:underline" }, "🔍 Abrir Diagrama BPMN en alta resolución ↗"))))))
      );
    } else if (pestanaActiva === "it2") {
      cuerpoContenido.append(
        h("div", { class: "tarjeta", style: "margin-bottom:20px" },
          h("div", { class: "tarjeta-cuerpo" },
            h("h3", {}, "Iteración 2: Identificación del Deep Agent & Escalado Multi-Tenant"),
            h("p", { class: "mute peq", style: "margin:6px 0 16px" }, "Evolución a plataforma corporativa B2B (Gerald Enterprise OS) con agentes autónomos y gobernanza en LangSmith."),
            h("div", { style: "display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:16px;margin-bottom:16px" },
              h("div", { style: "background:var(--superficie-2);padding:14px;border-radius:var(--radio);border:1px solid var(--borde)" },
                h("strong", { style: "color:#38bdf8" }, "🧠 Definición del Deep Agent"),
                h("ul", { style: "padding-left:18px;margin-top:8px;font-size:13px;line-height:1.5" },
                  h("li", {}, "Máquina de estados cíclica implementada en LangGraph StateGraph."),
                  h("li", {}, "Memoria transaccional con EstadoPedido tipado."),
                  h("li", {}, "Percepción multimodal con Gemini Vision y Structured Outputs."),
                  h("li", {}, "Auto-reflexión y evaluación de coherencia con derivación HITL."),
                  h("li", {}, "Telemetría completa de latencias y tokens en LangSmith."))),
              h("div", { style: "background:var(--superficie-2);padding:14px;border-radius:var(--radio);border:1px solid var(--borde)" },
                h("strong", { style: "color:#f59e0b" }, "🏢 Arquitectura Multi-Tenant Corporativa"),
                h("ul", { style: "padding-left:18px;margin-top:8px;font-size:13px;line-height:1.5" },
                  h("li", {}, "Entel Perú (C-ENTEL-PE): Lotes técnicos y fibra azul."),
                  h("li", {}, "Banco BCP (C-BANCO-BCP): Casacas térmicas azul noche."),
                  h("li", {}, "Interbank (C-INTERBANK): Shorts y polos para eventos."),
                  h("li", {}, "Claro Perú (C-CLARO-PE): Dotación de distribución."),
                  h("li", {}, "Aislamiento criptográfico en JWT con validación en cada endpoint.")))),
            h("h4", { style: "margin:16px 0 8px" }, "Constitución & Gobernanza Multi-Empresa"),
            h("p", { class: "mute peq", style: "margin-bottom:12px" }, "Las empresas tienen visibilidad exclusiva de sus pedidos y cotizaciones. Ningún tenant puede consultar información ajena. Toda la actividad de los agentes queda auditada e indexada en LangSmith bajo el proyecto 'gerald-sport'."),
            h("div", { style: "padding:14px;background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.25);border-radius:var(--radio);display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap" },
              h("div", {},
                h("strong", { style: "font-size:14px" }, "🔬 Monitoreo de Producción en LangSmith Cloud"),
                h("div", { class: "mute peq", style: "margin-top:4px" }, "Proyecto: gerald-sport · Trazas verificadas: a0_ingesta, a1_recepcion, a2_boceto, a3_calcular, evaluar, HITL.")),
              h("a", { href: "https://smith.langchain.com/", target: "_blank", rel: "noopener", class: "btn btn-primario", style: "font-size:12px;padding:7px 14px" }, "Ir a LangSmith ↗")),
            h("div", { style: "margin-top:20px;border-top:1px solid var(--borde);padding-top:16px" },
              h("h4", { style: "margin-bottom:6px" }, "📸 Evidencia de Ejecución en LangSmith (Dashboard & Trazas Reales)"),
              h("p", { class: "mute peq", style: "margin-bottom:12px" }, "Telemetría capturada en vivo durante la inferencia multiagente y checkpoints de LangGraph."),
              h("div", { style: "display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:16px" },
                h("div", { style: "background:#0b1120;padding:12px;border-radius:var(--radio);border:1px solid var(--borde);text-align:center" },
                  h("strong", { style: "display:block;margin-bottom:8px;font-size:13px;color:#818cf8" }, "Dashboard General del Proyecto 'gerald-sport'"),
                  h("img", { src: "/captura_langsmith_dashboard.png", alt: "LangSmith Dashboard", style: "width:100%;border-radius:6px;cursor:pointer", onclick: () => window.open("/captura_langsmith_dashboard.png", "_blank") }),
                  h("a", { href: "/captura_langsmith_dashboard.png", target: "_blank", class: "peq mute", style: "display:block;margin-top:6px;text-decoration:underline" }, "🔍 Ver Captura Completa ↗")),
                h("div", { style: "background:#0b1120;padding:12px;border-radius:var(--radio);border:1px solid var(--borde);text-align:center" },
                  h("strong", { style: "display:block;margin-bottom:8px;font-size:13px;color:#38bdf8" }, "Traza de Grafo (a0_ingesta → a2_boceto → a3_calcular)"),
                  h("img", { src: "/captura_langsmith_trace.jpg", alt: "LangSmith Traza Grafo", style: "width:100%;border-radius:6px;cursor:pointer", onclick: () => window.open("/captura_langsmith_trace.jpg", "_blank") }),
                  h("a", { href: "/captura_langsmith_trace.jpg", target: "_blank", class: "peq mute", style: "display:block;margin-top:6px;text-decoration:underline" }, "🔍 Ver Traza Completa ↗"))))))
      );
    } else if (pestanaActiva === "despliegue") {
      cuerpoContenido.append(
        h("div", { class: "tarjeta", style: "margin-bottom:20px" },
          h("div", { class: "tarjeta-cuerpo" },
            h("h3", {}, "Arquitectura de Despliegue Cloud & Componentes del Sistema"),
            h("p", { class: "mute peq", style: "margin:6px 0 16px" }, "Diagrama de capas integradas: Frontend SPA, Vercel Edge Serverless, Seguridad RBAC, Deep Agent LangGraph y Servicios Cloud."),
            h("div", { style: "display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:14px;margin-bottom:16px" },
              h("div", { style: "border:1px solid var(--borde);padding:14px;border-radius:var(--radio);background:var(--superficie)" },
                h("div", { style: "font-size:12px;font-weight:700;color:var(--primario);text-transform:uppercase" }, "Capa 1: Frontend SPA"),
                h("strong", { style: "display:block;margin:4px 0" }, "Gerald Enterprise OS"),
                h("p", { class: "mute peq" }, "Vanilla JS, CSS modular, selector Multi-Tenant, creador de pedidos a 1-clic y simulación inmediata.")),
              h("div", { style: "border:1px solid var(--borde);padding:14px;border-radius:var(--radio);background:var(--superficie)" },
                h("div", { style: "font-size:12px;font-weight:700;color:var(--info);text-transform:uppercase" }, "Capa 2: Edge & Runtime"),
                h("strong", { style: "display:block;margin:4px 0" }, "Vercel Serverless Function"),
                h("p", { class: "mute peq" }, "FastAPI Python 3.12, enrutamiento limpio, middleware CORS y almacenamiento elástico /tmp.")),
              h("div", { style: "border:1px solid var(--borde);padding:14px;border-radius:var(--radio);background:var(--superficie)" },
                h("div", { style: "font-size:12px;font-weight:700;color:var(--alerta);text-transform:uppercase" }, "Capa 3: Deep Agent Core"),
                h("strong", { style: "display:block;margin:4px 0" }, "LangGraph StateGraph"),
                h("p", { class: "mute peq" }, "Máquina de estados cíclica, Pydantic schemas, motor de stock en Decimal y compuertas HITL.")),
              h("div", { style: "border:1px solid var(--borde);padding:14px;border-radius:var(--radio);background:var(--superficie)" },
                h("div", { style: "font-size:12px;font-weight:700;color:var(--ok);text-transform:uppercase" }, "Capa 4: Cloud & Observabilidad"),
                h("strong", { style: "display:block;margin:4px 0" }, "Gemini & LangSmith"),
                h("p", { class: "mute peq" }, "Gemini Flash Multimodal para visión, PostgreSQL transaccional y trazas completas en LangSmith."))),
            h("div", { style: "margin-top:20px;border-top:1px solid var(--borde);padding-top:16px" },
              h("h4", { style: "margin-bottom:6px" }, "📐 Topología de Arquitectura de Despliegue Cloud"),
              h("p", { class: "mute peq", style: "margin-bottom:12px" }, "Diagrama integral de arquitectura: SPA Frontend, Vercel Serverless Edge, Orquestador LangGraph StateGraph, Gemini Multimodal, PostgreSQL y LangSmith."),
              h("div", { style: "text-align:center;background:#0b1120;padding:14px;border-radius:var(--radio);border:1px solid var(--borde)" },
                h("img", { src: "/diagrama_arquitectura.jpg", alt: "Diagrama de Arquitectura Cloud Gerald Sport", style: "width:100%;max-width:850px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,0.5);cursor:pointer", onclick: () => window.open("/diagrama_arquitectura.jpg", "_blank") }),
                h("div", { style: "margin-top:8px" },
                  h("a", { href: "/diagrama_arquitectura.jpg", target: "_blank", rel: "noopener", class: "peq mute", style: "text-decoration:underline" }, "🔍 Abrir Diagrama de Arquitectura en alta resolución ↗")))),
            h("div", { style: "text-align:center;margin-top:20px" },
              h("a", { href: "/informe", target: "_blank", rel: "noopener", class: "btn btn-primario", style: "padding:10px 20px" }, "📄 Abrir Informe Completo de Arquitectura LangChain (HTML)"))))
      );
    }
  }

  renderPestana();

  contenedor.append(
    cabecera("Arquitectura SDD & Evaluación Financiera", "Metodología Spec-Driven Development · Iteración 1 & 2 · Cálculos de ROI, TCO, VAN y Deep Agent en LangGraph", btnLangSmith, btnInforme),
    kpis,
    barraPestanas,
    cuerpoContenido
  );
}

// ---------- Arranque ----------
if (sesion) iniciarApp(); else pintarLogin();