/* Portal Gerald Sport. Sin dependencias. Todo texto se inserta con textContent (nunca innerHTML). */
"use strict";

// ---------- utilidades ----------
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
  const t = h("div", { class: "toast " + tipo, role: "status" }, texto);
  document.getElementById("avisos").append(t);
  setTimeout(() => t.remove(), 4500);
}

const almacen = {
  leer(k) { try { return JSON.parse(sessionStorage.getItem(k)); } catch { return null; } },
  guardar(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
  borrar(k) { try { sessionStorage.removeItem(k); } catch { /* sin almacenamiento */ } },
};

// ---------- sesión y API ----------
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

// ---------- vocabulario del BPMN ----------
const ESTADOS = {
  recibido: ["Recibido", "proceso"], validado: ["Validando", "proceso"],
  interpretado: ["Interpretando boceto", "proceso"], calculado: ["Calculando costo", "proceso"],
  en_revision: ["En revisión", "alerta"], cotizado: ["Cotización lista", "accion"],
  contratado: ["Contratado", "ok"], esperando_abastecimiento: ["Esperando materiales", "alerta"],
  reservado: ["Materiales reservados", "ok"], en_produccion: ["En producción", "ok"],
  observado: ["Requiere corrección", "error"], duplicado: ["Duplicado", "neutro"],
  no_contratado: ["No contratado", "neutro"], pendiente_reproceso: ["Reintentando", "alerta"],
  detenido: ["Detenido", "error"],
};
const PASOS = ["Recibido", "Evaluación", "Cotización", "Contrato", "Materiales", "Producción"];
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

// ---------- inicio de sesión ----------
const ROLES = [
  { rol: "cliente", titulo: "Cliente", texto: "Enviar pedidos y aceptar cotizaciones", id: "C-001" },
  { rol: "administrador", titulo: "Administrador", texto: "Revisar casos de excepción", id: "ADM-1" },
  { rol: "almacen", titulo: "Almacén", texto: "Abastecer materiales faltantes", id: "ALM-1" },
  { rol: "auditor", titulo: "Auditor", texto: "Calibración y gobernanza", id: "AUD-1" },
];

async function pintarLogin() {
  let demo = false;
  try { demo = (await (await fetch("/demo/estado")).json()).demo; } catch { /* API caída */ }
  let elegido = ROLES[0];
  const idInput = h("input", { type: "text", value: elegido.id, "aria-label": "Identificador", autocomplete: "off" });
  const botones = ROLES.map((r) => h("button", {
    type: "button", class: "rol", "aria-pressed": String(r === elegido),
    onclick: () => {
      elegido = r; idInput.value = r.id;
      botones.forEach((b, i) => b.setAttribute("aria-pressed", String(ROLES[i] === r)));
    },
  }, h("strong", {}, r.titulo), h("span", {}, r.texto)));

  const tokenInput = h("textarea", { placeholder: "Pegue aquí su token de acceso", rows: 3 });
  const enviar = h("button", { class: "btn btn-primario btn-grande", type: "submit" }, "Ingresar");

  const formulario = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      enviar.disabled = true;
      try {
        if (demo) {
          const r = await api("/demo/sesion", { method: "POST", json: { rol: elegido.rol, id: idInput.value.trim() } });
          sesion = { token: r.token, rol: r.rol, id: r.id };
        } else {
          const token = tokenInput.value.trim();
          const datos = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
          sesion = { token, rol: datos.rol, id: datos.sub };
        }
        almacen.guardar("gs_sesion", sesion);
        iniciarApp();
      } catch (err) {
        aviso(err.message.includes("JSON") || err.message.includes("atob") ? "Token inválido" : err.message, "error");
      } finally { enviar.disabled = false; }
    },
  },
  demo ? [h("div", { class: "roles" }, botones), h("label", { class: "campo" }, h("span", {}, "Identificador"), idInput)]
       : h("label", { class: "campo" }, h("span", {}, "Token de acceso"), tokenInput),
  enviar);

  $raiz().replaceChildren(h("div", { class: "login" }, h("div", { class: "login-tarjeta" },
    h("div", { class: "login-marca" }, h("div", { class: "logo" }, "GS"), h("h1", {}, "Gerald Sport")),
    h("p", { class: "lema" }, "Portal de pedidos y coordinación de materiales"),
    formulario,
    demo && h("div", { class: "nota-demo" },
      "Modo demostración: elija un rol para probar cada carril del proceso. Los datos se guardan en memoria."),
  )));
}

// ---------- marco de la aplicación ----------
const VISTAS = {
  cliente: [["nuevo", "Nuevo pedido"], ["mis", "Mis pedidos"]],
  administrador: [["bandeja", "Bandeja de revisión"], ["calibracion", "Calibración"]],
  almacen: [["faltantes", "Faltantes"]],
  auditor: [["calibracion", "Calibración"]],
};
const NOMBRE_ROL = { cliente: "Cliente", administrador: "Administrador", almacen: "Almacén", auditor: "Auditor" };
let vistaActual = null;
let sondeo = null;
let contenedor = null;
let navBotones = {};

function detenerSondeo() { if (sondeo) { clearInterval(sondeo); sondeo = null; } }
function sondear(fn, ms = 3000) { detenerSondeo(); sondeo = setInterval(() => fn().catch(() => {}), ms); }

function iniciarApp() {
  const vistas = VISTAS[sesion.rol] || [];
  navBotones = {};
  const nav = h("nav", { "aria-label": "Secciones" }, vistas.map(([clave, titulo]) => {
    const b = h("button", { onclick: () => irA(clave) }, titulo);
    navBotones[clave] = b;
    return b;
  }));
  contenedor = h("main", {});
  $raiz().replaceChildren(
    h("header", { class: "barra" },
      h("div", { class: "marca" }, h("div", { class: "logo" }, "GS"), h("span", {}, "Gerald Sport")),
      nav,
      h("div", { class: "usuario" },
        h("span", { class: "chip-rol" }, NOMBRE_ROL[sesion.rol]),
        h("span", {}, sesion.id),
        h("button", { class: "btn btn-texto", onclick: cerrarSesion }, "Salir"))),
    contenedor);
  irA(vistas[0][0]);
}

function irA(clave, extra) {
  detenerSondeo();
  vistaActual = clave;
  Object.entries(navBotones).forEach(([k, b]) => { if (k === clave) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); });
  contenedor.replaceChildren();
  ({ nuevo: vistaNuevo, mis: vistaMis, bandeja: vistaBandeja, calibracion: vistaCalibracion, faltantes: vistaFaltantes })[clave](extra);
}

function cabecera(titulo, subtitulo, ...derecha) {
  return h("div", { class: "cabecera" }, h("div", {}, h("h2", {}, titulo), subtitulo && h("p", {}, subtitulo)), h("div", { class: "acciones" }, derecha));
}
function vacio(icono, titulo, texto) {
  return h("div", { class: "vacio" }, h("div", { class: "icono", "aria-hidden": "true" }, icono), h("strong", {}, titulo), texto);
}

// ---------- CLIENTE: nuevo pedido ----------
let catalogo = null;
async function obtenerCatalogo() {
  if (!catalogo) catalogo = (await api("/catalogo")).prendas;
  return catalogo;
}

async function vistaNuevo(prellenado) {
  const prendas = await obtenerCatalogo();
  const nombres = Object.keys(prendas);
  const lineas = [];
  const cajaLineas = h("div", { class: "lineas" });
  const resumen = h("ul", { class: "resumen-lista" });
  const totalPrendas = h("strong", {}, "0");
  let archivo = null;

  function refrescarResumen() {
    const datos = lineas.map((l) => l.leer());
    resumen.replaceChildren(...datos.filter((d) => d.cantidad > 0).map((d) =>
      h("li", {}, h("span", {}, `${d.prenda} · ${d.talla} · ${d.color || "sin color"}`), h("strong", {}, d.cantidad))));
    if (!resumen.children.length) resumen.append(h("li", { class: "mute" }, "Agregue al menos una línea"));
    totalPrendas.textContent = datos.reduce((s, d) => s + (d.cantidad || 0), 0);
  }

  function agregarLinea(inicial = {}) {
    const prenda = h("select", { "aria-label": "Prenda" }, nombres.map((n) => h("option", { value: n }, n[0].toUpperCase() + n.slice(1))));
    const talla = h("select", { "aria-label": "Talla" });
    const color = h("input", { type: "text", placeholder: "Ej. azul marino", maxlength: 40, value: inicial.color || "" });
    const cantidad = h("input", { type: "number", min: 1, max: 1000, value: inicial.cantidad || 10 });
    const llenarTallas = () => {
      const previa = talla.value || inicial.talla;
      talla.replaceChildren(...prendas[prenda.value].map((t) => h("option", { value: t }, t)));
      if (prendas[prenda.value].includes(previa)) talla.value = previa;
    };
    if (inicial.prenda && prendas[inicial.prenda]) prenda.value = inicial.prenda;
    llenarTallas();
    const fila = h("div", { class: "linea" },
      h("label", { class: "campo" }, h("span", {}, "Prenda"), prenda),
      h("label", { class: "campo" }, h("span", {}, "Talla"), talla),
      h("label", { class: "campo" }, h("span", {}, "Color"), color),
      h("label", { class: "campo" }, h("span", {}, "Cantidad"), cantidad),
      h("button", { type: "button", class: "btn btn-texto quitar", title: "Quitar línea", "aria-label": "Quitar línea",
        onclick: () => { if (lineas.length > 1) { lineas.splice(lineas.indexOf(registro), 1); fila.remove(); refrescarResumen(); } } }, "✕"));
    const registro = { leer: () => ({ prenda: prenda.value, talla: talla.value, color: color.value.trim(), cantidad: parseInt(cantidad.value, 10) || 0 }) };
    prenda.addEventListener("change", () => { llenarTallas(); refrescarResumen(); });
    [talla, color, cantidad].forEach((el) => el.addEventListener("input", refrescarResumen));
    lineas.push(registro);
    cajaLineas.append(fila);
    refrescarResumen();
  }

  (prellenado?.lineas?.length ? prellenado.lineas : [{}]).forEach(agregarLinea);

  const entradaArchivo = h("input", { type: "file", accept: "image/png,image/jpeg,application/pdf", hidden: true });
  const previa = h("div", {});
  const zona = h("div", { class: "zona-archivo", tabindex: 0, role: "button",
    onclick: () => entradaArchivo.click(),
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); entradaArchivo.click(); } },
    ondragover: (e) => { e.preventDefault(); zona.classList.add("sobre"); },
    ondragleave: () => zona.classList.remove("sobre"),
    ondrop: (e) => { e.preventDefault(); zona.classList.remove("sobre"); elegirArchivo(e.dataTransfer.files[0]); },
  }, h("strong", {}, "Arrastre su boceto aquí o haga clic para elegirlo"), h("span", { class: "mute peq" }, "JPG, PNG o PDF · máximo 10 MB"), previa);
  entradaArchivo.addEventListener("change", () => elegirArchivo(entradaArchivo.files[0]));

  function elegirArchivo(f) {
    if (!f) return;
    if (!["image/png", "image/jpeg", "application/pdf"].includes(f.type)) return aviso("Use un archivo JPG, PNG o PDF", "error");
    if (f.size > 10 * 1024 * 1024) return aviso("El archivo supera los 10 MB", "error");
    archivo = f;
    previa.replaceChildren(f.type === "application/pdf"
      ? h("p", { class: "peq" }, "📄 " + f.name)
      : h("img", { class: "vista-previa", src: URL.createObjectURL(f), alt: "Vista previa del boceto" }));
  }

  const notas = h("textarea", { maxlength: 500, placeholder: "Indicaciones adicionales (opcional): ubicación del logo, tipografía, numeración…" });
  if (prellenado?.notas) notas.value = prellenado.notas;
  const enviar = h("button", { class: "btn btn-primario btn-grande", type: "submit", style: "width:100%" }, "Enviar pedido");

  const formulario = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      const datos = lineas.map((l) => l.leer());
      if (datos.some((d) => d.color.length < 2)) return aviso("Indique el color de cada línea", "error");
      if (datos.some((d) => d.cantidad < 1 || d.cantidad > 1000)) return aviso("Cada cantidad debe estar entre 1 y 1000", "error");
      if (!archivo) return aviso("Adjunte el boceto del diseño", "error");
      enviar.disabled = true;
      enviar.replaceChildren(h("span", { class: "cargando" }), "Enviando…");
      try {
        const fd = new FormData();
        fd.append("datos", JSON.stringify({ lineas: datos, notas: notas.value.trim() || null }));
        fd.append("archivo", archivo);
        const r = await api("/pedidos", { method: "POST", body: fd });
        recordarPedido(r.pedido_id);
        aviso(`Pedido ${r.pedido_id} enviado. Lo estamos procesando.`, "ok");
        irA("mis", r.pedido_id);
      } catch (err) {
        aviso(err.message, "error");
        enviar.disabled = false;
        enviar.textContent = "Enviar pedido";
      }
    },
  },
  h("div", { class: "rejilla-pedido" },
    h("div", {},
      h("section", { class: "tarjeta" }, h("div", { class: "tarjeta-cuerpo" },
        h("h3", { style: "margin-bottom:14px" }, "1. Prendas"),
        cajaLineas,
        h("button", { type: "button", class: "btn", style: "margin-top:12px", onclick: () => agregarLinea() }, "+ Agregar línea"))),
      h("section", { class: "tarjeta" }, h("div", { class: "tarjeta-cuerpo" },
        h("h3", { style: "margin-bottom:14px" }, "2. Boceto del diseño"), zona, entradaArchivo,
        h("label", { class: "campo", style: "margin-top:16px" }, h("span", {}, "Notas"), notas)))),
    h("aside", { class: "tarjeta", style: "position:sticky;top:80px" }, h("div", { class: "tarjeta-cuerpo" },
      h("h3", { style: "margin-bottom:14px" }, "Resumen"), resumen,
      h("div", { class: "resumen-total" }, h("span", { class: "mute" }, "Total de prendas"), totalPrendas),
      enviar,
      h("p", { class: "mute peq", style: "margin:12px 0 0" },
        "Validamos su pedido, calculamos materiales y le enviamos la cotización. Solo tendrá que aceptarla con un clic.")))));

  contenedor.append(
    cabecera(prellenado ? "Corregir pedido" : "Nuevo pedido",
      prellenado ? "Ajuste lo indicado en las observaciones y vuelva a enviarlo." : "Envíe su pedido una sola vez: boceto, tallas, colores y cantidades."),
    formulario);
}

// ---------- CLIENTE: mis pedidos ----------
function recordarPedido(id) {
  const ids = new Set(almacen.leer("gs_recientes_" + sesion.id) || []);
  ids.add(id);
  almacen.guardar("gs_recientes_" + sesion.id, [...ids].slice(-30));
}

async function cargarMisPedidos() {
  const { pedidos } = await api("/pedidos");
  const conocidos = new Set(pedidos.map((p) => p.pedido_id));
  // Pedidos observados en la validación o duplicados no llegan a registrarse: se siguen por su número.
  const recientes = (almacen.leer("gs_recientes_" + sesion.id) || []).filter((id) => !conocidos.has(id));
  const extra = await Promise.all(recientes.map((id) => api("/pedidos/" + id).catch(() => null)));
  return [...extra.filter(Boolean).reverse(), ...pedidos];
}

async function vistaMis(seleccion) {
  const lista = h("div", { class: "lista-pedidos" });
  const detalle = h("section", { class: "tarjeta" });
  let pedidos = [];
  let elegido = seleccion || null;
  const avisados = new Set();

  contenedor.append(
    cabecera("Mis pedidos", "Siga el avance de cada pedido. Le avisaremos cuando requiera su acción.",
      h("button", { class: "btn btn-primario", onclick: () => irA("nuevo") }, "+ Nuevo pedido")),
    h("div", { class: "dos-columnas" }, lista, detalle));

  async function refrescar() {
    pedidos = await cargarMisPedidos();
    if (!elegido && pedidos.length) elegido = pedidos[0].pedido_id;
    for (const p of pedidos) {
      if (p.pausa?.tipo === "aceptacion_cliente" && !avisados.has(p.pedido_id)) {
        avisados.add(p.pedido_id);
        if (seleccion === p.pedido_id) aviso("Su cotización está lista", "ok");
      }
    }
    pintarLista();
    pintarDetalle();
  }

  function pintarLista() {
    if (!pedidos.length) {
      lista.replaceChildren(h("div", { class: "tarjeta" }, vacio("👕", "Aún no tiene pedidos", "Envíe su primer pedido para verlo aquí.")));
      return;
    }
    lista.replaceChildren(...pedidos.map((p) => h("button", {
      class: "item-pedido", "aria-current": String(p.pedido_id === elegido),
      onclick: () => { elegido = p.pedido_id; pintarLista(); pintarDetalle(); },
    },
    h("div", { class: "fila" }, h("strong", { class: "mono" }, p.pedido_id), chipEstado(p.estado)),
    h("span", { class: "mute peq" }, resumenLineas(p.lineas)),
    p.pausa?.tipo === "aceptacion_cliente" && h("span", { class: "peq", style: "color:var(--acento);font-weight:600" }, "Requiere su aceptación →"))));
  }

  function pintarDetalle() {
    const p = pedidos.find((x) => x.pedido_id === elegido);
    if (!p) { detalle.replaceChildren(vacio("📋", "Seleccione un pedido", "")); return; }
    const paso = PASO_DE[p.estado] ?? 0;
    const terminal = ["observado", "duplicado", "no_contratado", "detenido"].includes(p.estado);

    const cuerpo = h("div", { class: "tarjeta-cuerpo" },
      h("div", { class: "fila", style: "display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;gap:8px;flex-wrap:wrap" },
        h("div", {}, h("span", { class: "mute peq" }, "Pedido"), h("h2", { class: "mono", style: "font-size:20px" }, p.pedido_id)),
        chipEstado(p.estado)),
      !terminal && h("div", { class: "pasos", role: "list" }, PASOS.map((nombre, i) =>
        h("div", { role: "listitem", class: "paso " + (i < paso ? "hecho" : i === paso ? "actual" : "") },
          h("div", { class: "punto" }, i < paso ? "✓" : i + 1), nombre))));

    if (p.estado === "observado") {
      cuerpo.append(h("div", { class: "aviso error" },
        h("strong", {}, "Su pedido necesita ajustes antes de continuar"),
        h("ul", {}, (p.observaciones.length ? p.observaciones : ["Revise los datos del pedido."]).map((o) => h("li", {}, o))),
        h("div", {}, h("button", { class: "btn btn-primario", style: "margin-top:6px",
          onclick: () => irA("nuevo", { lineas: p.lineas, notas: p.notas }) }, "Corregir y reenviar"))));
    } else if (p.estado === "duplicado") {
      cuerpo.append(h("div", { class: "aviso info" }, h("strong", {}, "Este pedido ya estaba registrado"),
        "No es necesario enviarlo de nuevo; siga el pedido original en su lista."));
    } else if (p.estado === "no_contratado") {
      cuerpo.append(h("div", { class: "aviso info" }, h("strong", {}, "Pedido cerrado sin contratar"), "Puede enviar un nuevo pedido cuando lo desee."));
    } else if (p.estado === "detenido" || p.estado === "pendiente_reproceso") {
      cuerpo.append(h("div", { class: "aviso alerta" }, h("strong", {}, "Estamos resolviendo un inconveniente técnico"),
        "Su pedido está a salvo y continuará automáticamente. No necesita volver a enviarlo."));
    } else if (p.estado === "en_revision") {
      cuerpo.append(h("div", { class: "aviso info" }, h("strong", {}, "Un especialista está revisando su pedido"),
        "Recibirá la cotización en cuanto se apruebe (normalmente en menos de 24 horas)."));
    } else if (p.estado === "esperando_abastecimiento") {
      cuerpo.append(h("div", { class: "aviso info" }, h("strong", {}, "Contrato registrado"),
        "Estamos completando algunos materiales con el almacén; la producción inicia en cuanto lleguen."));
    } else if (p.estado === "en_produccion") {
      cuerpo.append(h("div", { class: "aviso ok" }, h("strong", {}, "¡Su pedido está en producción!"),
        "Le enviamos la fecha estimada de entrega a su correo."));
    } else if (EN_PROCESO.has(p.estado)) {
      cuerpo.append(h("div", { class: "aviso info" }, h("strong", {}, h("span", { class: "cargando", style: "width:12px;height:12px;margin-right:8px" }), "Procesando su pedido"),
        "Validamos los datos, interpretamos el boceto y calculamos materiales. Esto toma unos segundos."));
    }

    if (p.pausa?.tipo === "aceptacion_cliente") {
      const botones = [
        h("button", { class: "btn btn-ok btn-grande", onclick: () => responder(true) }, "Aceptar cotización y contrato"),
        h("button", { class: "btn btn-texto", onclick: () => responder(false) }, "No acepto"),
      ];
      async function responder(acepta) {
        if (!acepta && !confirm("¿Confirma que no desea contratar este pedido?")) return;
        botones.forEach((b) => (b.disabled = true));
        try {
          await api(`/pedidos/${p.pedido_id}/aceptacion`, { method: "POST", json: { acepta } });
          aviso(acepta ? "¡Gracias! Su contrato quedó registrado." : "Pedido cerrado.", "ok");
          await refrescar();
        } catch (err) { aviso(err.message, "error"); botones.forEach((b) => (b.disabled = false)); }
      }
      cuerpo.append(h("div", { class: "cotizacion" },
        h("div", {}, h("span", { class: "mute peq" }, "Cotización"), h("div", { class: "monto" }, soles(p.pausa.costo_total_pen))),
        h("span", { class: "peq" }, "Incluye telas, insumos y confección según su boceto. Al aceptar se registra el contrato y se reservan los materiales."),
        h("div", { class: "acciones" }, botones)));
    }

    if (p.actividad?.length) {
      cuerpo.append(h("h3", { style: "margin:8px 0 12px" }, "Actividad del sistema multiagente"), lineaActividad(p.actividad));
    }
    cuerpo.append(
      h("h3", { style: "margin:8px 0 10px" }, "Detalle"),
      h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Prenda"), h("th", {}, "Talla"), h("th", {}, "Color"), h("th", { class: "num" }, "Cantidad"))),
        h("tbody", {}, p.lineas.map((l) => h("tr", {}, h("td", {}, l.prenda), h("td", {}, l.talla), h("td", {}, l.color), h("td", { class: "num" }, l.cantidad)))),
        p.costo_total_pen && !p.pausa && h("tfoot", {}, h("tr", {}, h("td", { colspan: 3 }, "Total"), h("td", { class: "num" }, soles(p.costo_total_pen))))),
      p.notas && h("p", { class: "mute peq" }, "Notas: " + p.notas));
    const caja = h("div", { style: "margin-top:16px" });
    cuerpo.append(caja);
    mostrarBoceto(p.pedido_id, caja);
    detalle.replaceChildren(cuerpo);
  }

  await refrescar();
  sondear(refrescar, 3000);
}

// Línea de tiempo de los agentes (reconstruida en el servidor desde los checkpoints de LangGraph).
const SIGLA = {
  "A0 Ingesta": "A0", "A1 Recepción": "A1", "A2 Boceto": "A2", "A3 Materiales": "A3", "A4 Registro": "A4",
  "Orquestador": "OR", "Administrador": "AD", "Cliente": "CL", "Almacén": "AL",
};
const hora = (m) => m ? new Date(m).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
function lineaActividad(actividad) {
  return h("ol", { class: "actividad" }, actividad.map((p) => h("li", { class: `${p.carril} ${p.estado}` },
    h("div", { class: "nodo-act", "data-agente": SIGLA[p.agente] || "", "aria-hidden": "true" }, SIGLA[p.agente] || "·"),
    h("div", { class: "act-cuerpo" },
      h("div", { class: "act-cab" },
        h("strong", {}, p.agente),
        p.carril === "humano" && h("span", { class: "chip-humano" }, "intervención humana"),
        p.estado === "esperando" && h("span", { class: "estado accion" }, "pendiente"),
        h("span", { class: "mute peq act-hora" }, hora(p.momento))),
      h("div", { class: "peq" }, p.detalle)))));
}

// Carga el boceto con el token (un <img src> no puede enviar la cabecera de autorización).
const cacheBocetos = new Map();
async function mostrarBoceto(pedidoId, caja) {
  try {
    if (!cacheBocetos.has(pedidoId)) {
      const r = await api(`/pedidos/${pedidoId}/boceto`);
      cacheBocetos.set(pedidoId, { tipo: r.headers.get("content-type"), url: URL.createObjectURL(await r.blob()) });
    }
    const b = cacheBocetos.get(pedidoId);
    caja.replaceChildren(h("h3", { style: "margin-bottom:10px" }, "Boceto"), b.tipo === "application/pdf"
      ? h("div", { class: "boceto-pdf" }, h("a", { href: b.url, target: "_blank", rel: "noopener" }, "📄 Abrir boceto (PDF)"))
      : h("img", { class: "boceto", src: b.url, alt: "Boceto del pedido " + pedidoId }));
  } catch { /* boceto no disponible: se omite */ }
}

// ---------- ADMINISTRADOR: bandeja de revisión ----------
async function vistaBandeja() {
  const caja = h("div", {});
  const contador = h("span", {});
  contenedor.append(cabecera("Bandeja de revisión", "Solo llegan aquí los pedidos con confianza no alta o costo sobre el umbral.", contador), caja);
  let firma = "";

  async function refrescar() {
    const { pedidos } = await api("/revision");
    const nueva = pedidos.map((p) => p.pedido_id).join(",");
    if (nueva === firma) return;  // no repintar: conserva lo que el administrador está escribiendo
    firma = nueva;
    contador.replaceChildren(pedidos.length ? h("span", { class: "estado alerta" }, `${pedidos.length} por revisar`) : "");
    if (!pedidos.length) {
      caja.replaceChildren(h("div", { class: "tarjeta" }, vacio("✅", "No hay pedidos por revisar", "El sistema aprobó automáticamente los demás pedidos.")));
      return;
    }
    caja.replaceChildren(...pedidos.map(tarjetaRevision));
  }

  function tarjetaRevision(p) {
    const comentario = h("textarea", { placeholder: "Comentario para el cliente (obligatorio si rechaza)", maxlength: 500 });
    const botones = [
      h("button", { class: "btn btn-ok", onclick: () => decidir(true) }, "Aprobar y enviar cotización"),
      h("button", { class: "btn btn-peligro", onclick: () => decidir(false) }, "Rechazar con observación"),
    ];
    async function decidir(aprobado) {
      if (!aprobado && !comentario.value.trim()) { comentario.focus(); return aviso("Escriba el motivo del rechazo para el cliente", "error"); }
      botones.forEach((b) => (b.disabled = true));
      try {
        await api(`/revision/${p.pedido_id}`, { method: "POST", json: { aprobado, comentario: comentario.value.trim() } });
        aviso(aprobado ? `Pedido ${p.pedido_id} aprobado: cotización enviada.` : `Observación enviada al cliente.`, "ok");
        firma = "";
        await refrescar();
      } catch (err) { aviso(err.message, "error"); botones.forEach((b) => (b.disabled = false)); }
    }
    const boceto = h("div", {});
    mostrarBoceto(p.pedido_id, boceto);
    const materiales = p.materiales || [];
    return h("article", { class: "tarjeta" }, h("div", { class: "tarjeta-cuerpo" },
      h("div", { style: "display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:16px" },
        h("div", {}, h("h3", { class: "mono", style: "font-size:17px" }, p.pedido_id), h("span", { class: "mute peq" }, "Cliente " + p.cliente_id)),
        h("span", { class: "motivo" }, "⚠ " + (p.motivo || p.pausa?.motivo || "Revisión requerida").replace("Revisión requerida: ", ""))),
      h("div", { class: "revision" },
        h("div", {}, boceto,
          h("h3", { style: "margin:14px 0 8px" }, "Pedido"),
          h("ul", { style: "margin:0;padding-left:18px" }, p.lineas.map((l) => h("li", {}, `${l.cantidad} × ${l.prenda} ${l.talla} · ${l.color}`))),
          p.notas && h("p", { class: "mute peq" }, "Notas: " + p.notas)),
        h("div", {},
          h("details", { class: "act-plegable", open: true },
            h("summary", {}, "Qué hicieron los agentes antes de escalar"),
            lineaActividad(p.actividad || [])),
          h("h3", { style: "margin-bottom:8px" }, "Borrador de materiales y costo"),
          h("table", {},
            h("thead", {}, h("tr", {}, h("th", {}, "Material"), h("th", { class: "num" }, "Cantidad"), h("th", { class: "num" }, "Precio"), h("th", { class: "num" }, "Subtotal"))),
            h("tbody", {}, materiales.map((m) => h("tr", {},
              h("td", {}, m.nombre, h("div", { class: "mute peq mono" }, m.material_id)),
              h("td", { class: "num" }, `${Number(m.cantidad)} ${m.unidad}`),
              h("td", { class: "num" }, soles(m.precio_unitario_pen)),
              h("td", { class: "num" }, soles(m.subtotal_pen))))),
            h("tfoot", {}, h("tr", {}, h("td", { colspan: 3 }, "Total"), h("td", { class: "num" }, soles(p.costo_total_pen))))),
          h("label", { class: "campo", style: "margin-top:16px" }, h("span", {}, "Comentario"), comentario),
          h("div", { class: "acciones", style: "margin-top:12px" }, botones)))));
  }

  await refrescar();
  sondear(refrescar, 4000);
}

// ---------- GOBERNANZA: calibración ----------
async function vistaCalibracion() {
  const dias = h("select", { "aria-label": "Periodo" }, [7, 30, 90].map((d) => h("option", { value: d }, `Últimos ${d} días`)));
  const caja = h("div", {});
  contenedor.append(cabecera("Calibración", "¿Acierta el sistema cuando dice tener confianza alta? Las sugerencias no se aplican solas.", dias), caja);

  async function refrescar() {
    const r = await api("/calibracion?dias=" + dias.value);
    const tiles = ["alta", "media", "baja"].map((nivel) => {
      const t = r.por_confianza[nivel];
      const exito = t.pedidos ? Math.round((t.contratados / t.pedidos) * 100) : 0;
      return h("div", { class: "tarjeta tile" },
        h("div", { class: "etiqueta" }, "Confianza " + nivel),
        h("div", { class: "valor" }, t.pedidos, h("span", { class: "mute", style: "font-size:15px;font-weight:500" }, " pedidos")),
        h("div", { class: "peq" }, `${t.contratados} contratados · ${t.fallidos} fallidos · fallo ${(t.tasa_fallo * 100).toFixed(1)} %`),
        h("div", { class: "barra-progreso", title: `${exito} % contratados` }, h("div", { class: t.tasa_fallo > 0.05 ? "fallo" : "", style: `width:${exito}%` })));
    });
    caja.replaceChildren(
      r.deriva
        ? h("div", { class: "aviso error" }, h("strong", {}, "Deriva detectada"), "Los pedidos con confianza alta fallan más del 5 %. Revise los umbrales.")
        : h("div", { class: "aviso ok" }, h("strong", {}, "Sin deriva"), `${r.total} decisiones etiquetadas en el periodo.`),
      h("div", { class: "tiles" }, tiles),
      h("div", { class: "tarjeta" }, h("div", { class: "tarjeta-cuerpo" }, h("h3", { style: "margin-bottom:10px" }, "Sugerencias para el administrador"),
        r.sugerencias.length ? h("ul", { style: "margin:0;padding-left:18px" }, r.sugerencias.map((s) => h("li", {}, s))) : h("p", { class: "mute" }, "Sin sugerencias por ahora."))));
  }
  dias.addEventListener("change", () => refrescar().catch((e) => aviso(e.message, "error")));
  await refrescar();
}

// ---------- ALMACÉN: faltantes ----------
async function vistaFaltantes() {
  const caja = h("div", {});
  contenedor.append(cabecera("Materiales faltantes", "Registre el ingreso cuando llegue el material: los pedidos en espera continúan solos."), caja);
  let firma = "";

  async function refrescar() {
    const { requerimientos } = await api("/almacen/requerimientos");
    const nueva = JSON.stringify(requerimientos);
    if (nueva === firma) return;
    firma = nueva;
    if (!requerimientos.length) {
      caja.replaceChildren(h("div", { class: "tarjeta" }, vacio("📦", "Sin faltantes pendientes", "Todo el material requerido está en stock.")));
      return;
    }
    caja.replaceChildren(h("div", { class: "tarjeta" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Pedido"), h("th", {}, "Material"), h("th", { class: "num" }, "Faltante"), h("th", { class: "num" }, "Stock actual"), h("th", {}, "Registrar ingreso"))),
      h("tbody", {}, requerimientos.map((r) => {
        const cantidad = h("input", { type: "number", min: "0.01", step: "0.01", value: Math.ceil(Number(r.faltante)), style: "max-width:110px", "aria-label": "Cantidad ingresada" });
        const boton = h("button", { class: "btn btn-primario", onclick: async () => {
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
        } }, "Registrar");
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

// ---------- arranque ----------
if (sesion) iniciarApp(); else pintarLogin();
