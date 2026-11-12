/**
 * Intermediario entre la web (pública, sin credenciales) y GitHub Actions.
 *
 *   GET  /estado  -> cómo va la última actualización y si se puede lanzar otra
 *   POST /lanzar  -> lanza el workflow de actualización
 *
 * El token vive solo aquí, como secreto GITHUB_TOKEN. Para que nadie encadene
 * trabajos, no se lanza otro si hay uno en curso o si el último empezó hace
 * menos de MINUTOS_ENTRE_LANZAMIENTOS. Ese estado se lee de GitHub: no hay base de datos.
 */

async function github(env, ruta, opciones = {}) {
  const resp = await fetch(`https://api.github.com/repos/${env.REPO}${ruta}`, {
    ...opciones,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "produccion-industrial-actualizar",
    },
  });
  if (!resp.ok) throw new Error(`GitHub respondió ${resp.status}`);
  return resp.status === 204 ? null : resp.json();
}

async function estado(env) {
  const { workflow_runs: lista } = await github(env, `/actions/workflows/${env.WORKFLOW}/runs?per_page=1`);
  const ultima = lista[0];
  const espera = Number(env.MINUTOS_ENTRE_LANZAMIENTOS) || 60;
  if (!ultima) return { estado: "libre", ultimo: null, puede_lanzar: true, espera_min: 0 };

  const enCurso = ultima.status !== "completed";
  const minutos = (Date.now() - new Date(ultima.created_at).getTime()) / 60000;
  const faltan = enCurso ? 0 : Math.max(0, Math.ceil(espera - minutos));
  return {
    estado: enCurso ? "en_curso" : "libre",
    ultimo: { inicio: ultima.created_at, resultado: ultima.conclusion, url: ultima.html_url },
    puede_lanzar: !enCurso && faltan === 0,
    espera_min: faltan,
  };
}

export default {
  async fetch(peticion, env) {
    const origen = peticion.headers.get("Origin");
    const cors = {
      "Access-Control-Allow-Origin": env.ORIGEN_PERMITIDO,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      Vary: "Origin",
    };
    const json = (cuerpo, status = 200) =>
      new Response(JSON.stringify(cuerpo), {
        status,
        headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      });

    if (peticion.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (!env.GITHUB_TOKEN) return json({ error: "Falta configurar el secreto GITHUB_TOKEN" }, 500);

    const { pathname } = new URL(peticion.url);
    try {
      if (peticion.method === "GET" && pathname === "/estado") return json(await estado(env));

      if (peticion.method === "POST" && pathname === "/lanzar") {
        // Solo la web publicada puede lanzar (los navegadores siempre envían Origin en un POST).
        if (origen !== env.ORIGEN_PERMITIDO) return json({ error: "Origen no permitido" }, 403);
        const actual = await estado(env);
        if (!actual.puede_lanzar) return json({ ...actual, lanzado: false }, 429);
        const { default_branch: rama } = await github(env, "");
        await github(env, `/actions/workflows/${env.WORKFLOW}/dispatches`, {
          method: "POST",
          body: JSON.stringify({ ref: rama }),
        });
        return json({ estado: "en_curso", lanzado: true }, 202);
      }
      return json({ error: "No encontrado" }, 404);
    } catch (err) {
      return json({ error: err.message }, 502);
    }
  },
};
