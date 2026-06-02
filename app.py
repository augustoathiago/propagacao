import math
import random
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Prática Propagação de Incerteza",
    layout="wide",
    initial_sidebar_state="collapsed",
)

getcontext().prec = 50

SIGMA_INSTR = Decimal("0.05")  # mm (resolução do paquímetro)

# ============================================================
# ESTILO
# ============================================================
st.markdown(
    """
    <style>
        .main { padding-top: 1rem; }
        .section-card {
            padding: 1rem 1.2rem;
            border: 1px solid rgba(120,120,120,0.25);
            border-radius: 14px;
            background-color: rgba(250,250,250,0.60);
            margin-bottom: 1rem;
        }
        .result-box {
            padding: 0.9rem 1rem;
            border-radius: 12px;
            border: 1px solid rgba(0,0,0,0.15);
            background: #f7f9fc;
            margin-top: 0.5rem;
            margin-bottom: 0.7rem;
        }
        .small-note {
            font-size: 0.95rem;
            color: #444;
        }
        .foot {
            font-size: 0.92rem;
            color: #333;
        }
        .centered { text-align: center; }
        .muted { color: #666; }
        .math-box {
            padding: 0.7rem 0.9rem;
            border-left: 4px solid #4f81bd;
            background: #f6f9ff;
            border-radius: 8px;
            margin-top: 0.5rem;
            margin-bottom: 0.8rem;
        }
        table.custom-table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 0.4rem;
            margin-bottom: 0.8rem;
            font-size: 0.95rem;
        }
        table.custom-table th, table.custom-table td {
            border: 1px solid #d8d8d8;
            padding: 8px 10px;
            text-align: center;
            vertical-align: middle;
        }
        table.custom-table th {
            background: #eef4fb;
        }
        .highlight {
            background: #fff7e6;
            border: 1px solid #edd9a3;
            border-radius: 10px;
            padding: 0.8rem 1rem;
            margin: 0.6rem 0;
        }
        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def dec(x):
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def sqrt_decimal(x: Decimal) -> Decimal:
    x = dec(x)
    if x < 0:
        raise ValueError("Raiz de número negativo não é permitida.")
    return x.sqrt()


def fixed_str(x: Decimal, places: int) -> str:
    q = Decimal(1).scaleb(-places)
    y = dec(x).quantize(q, rounding=ROUND_HALF_EVEN)
    return f"{y:.{places}f}"


def plain_str(x: Decimal) -> str:
    x = dec(x)
    s = format(x, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s


def plain_str_limited(x: Decimal, places: int = 12) -> str:
    q = Decimal(1).scaleb(-places)
    y = dec(x).quantize(q, rounding=ROUND_HALF_EVEN)
    s = f"{y:.{places}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    if s == "-0":
        s = "0"
    return s


def count_decimal_places(x: Decimal) -> int:
    x = dec(x)
    exponent = x.as_tuple().exponent
    return -exponent if exponent < 0 else 0


def first_significant_digit(x: Decimal) -> int:
    x = abs(dec(x))
    if x == 0:
        return 0
    n = x.normalize()
    return int(n.as_tuple().digits[0])


def sig_digits_for_uncertainty(x: Decimal) -> int:
    """
    Regra:
    - 1 algarismo significativo;
    - exceto se o primeiro AS for 1 ou 2, então manter 2 AS.
    """
    fd = first_significant_digit(x)
    return 2 if fd in (1, 2) else 1


def round_sig_half_even(x: Decimal, sig_digits: int) -> Decimal:
    """
    Arredondamento por algarismos significativos usando ROUND_HALF_EVEN:
    - > 5 sobe
    - < 5 mantém
    - 5 exato (ou 5 seguido apenas de zeros) vai para o par
    """
    x = dec(x)
    if x == 0:
        return Decimal("0")
    exponent = x.adjusted()
    quant = Decimal(f"1e{exponent - sig_digits + 1}")
    return x.quantize(quant, rounding=ROUND_HALF_EVEN)


def round_uncertainty(x: Decimal) -> Decimal:
    x = abs(dec(x))
    if x == 0:
        return Decimal("0")
    n_sig = sig_digits_for_uncertainty(x)
    return round_sig_half_even(x, n_sig)


def round_value_to_match_uncertainty(value: Decimal, uncertainty: Decimal) -> Decimal:
    uncertainty = dec(uncertainty)
    value = dec(value)
    if uncertainty == 0:
        return value
    houses = count_decimal_places(uncertainty.normalize())
    q = Decimal(1).scaleb(-houses)
    return value.quantize(q, rounding=ROUND_HALF_EVEN)


def html_table(headers, rows):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        trs.append(f"<tr>{tds}</tr>")
    tbody = "".join(trs)
    return f"""
    <table class="custom-table">
        <thead><tr>{th}</tr></thead>
        <tbody>{tbody}</tbody>
    </table>
    """


def generate_measurements(center: Decimal, seed_key: str):
    """
    Gera cinco medições próximas do valor escolhido, quantizadas em 0,05 mm.
    """
    base = dec(center)
    step = Decimal("0.05")

    offset_seed = st.session_state.get(seed_key, random.randint(0, 10_000_000))
    rng = random.Random(offset_seed)

    possible_steps = [-4, -3, -2, -1, 0, 1, 2, 3, 4]

    values = []
    for _ in range(5):
        s = rng.choice(possible_steps)
        v = base + Decimal(s) * step
        if v <= 0:
            v = Decimal("0.05")
        values.append(v.quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN))

    # Evita todos iguais
    if len(set(values)) == 1:
        values[0] = (values[0] + step).quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN)

    return values


def calc_stats(values):
    n = Decimal(len(values))
    mean = sum(values, Decimal("0")) / n
    deviations = [v - mean for v in values]
    squares = [d * d for d in deviations]
    sum_sq = sum(squares, Decimal("0"))
    sigma_est = sqrt_decimal(sum_sq / (n * (n - 1)))
    return mean, deviations, squares, sum_sq, sigma_est


def calc_combined(sigma_est_rounded: Decimal, sigma_instr: Decimal = SIGMA_INSTR):
    return sqrt_decimal(dec(sigma_est_rounded) ** 2 + dec(sigma_instr) ** 2)


def cylinder_svg(d_mm: float, l_mm: float) -> str:
    """
    SVG de cilindro pseudo-3D, em container com rolagem horizontal no celular.
    Sem zoom; o usuário só arrasta/rola para ver tudo.
    """
    body_length_px = 420 + 6.0 * l_mm
    diameter_px = max(90, 70 + 3.6 * d_mm)

    margin_left = 150
    margin_right = 140
    margin_top = 70
    margin_bottom = 135

    x0 = margin_left
    y0 = margin_top + diameter_px / 2
    rx = diameter_px * 0.33
    ry = diameter_px * 0.18

    rect_h = diameter_px
    rect_y = y0 - rect_h / 2
    rect_x = x0 + rx
    rect_w = body_length_px

    total_w = rect_x + rect_w + rx + margin_right
    total_h = margin_top + diameter_px + margin_bottom

    # Cota do diâmetro
    dim_x = x0 - 65
    y1 = rect_y
    y2 = rect_y + rect_h

    # Cota do comprimento
    len_y = rect_y + rect_h + 58
    x1 = rect_x
    x2 = rect_x + rect_w

    return f"""
    <div style="
        width:100%;
        overflow-x:auto;
        overflow-y:hidden;
        border:1px solid rgba(100,100,100,0.25);
        border-radius:14px;
        padding:8px;
        background:#ffffff;
        -webkit-overflow-scrolling: touch;
        touch-action: pan-x pan-y;
    ">
      <svg
          width="{int(total_w)}"
          height="{int(total_h)}"
          viewBox="0 0 {int(total_w)} {int(total_h)}"
          xmlns="http://www.w3.org/2000/svg"
          style="display:block; max-width:none; user-select:none;"
          preserveAspectRatio="xMinYMin meet"
      >
        <defs>
          <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" style="stop-color:#dfeaf4;stop-opacity:1" />
            <stop offset="50%" style="stop-color:#b8d0e3;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#87afd0;stop-opacity:1" />
          </linearGradient>
          <linearGradient id="faceGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#f4f9fd;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#96bad7;stop-opacity:1" />
          </linearGradient>
          <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#111"/>
          </marker>
          <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.22"/>
          </filter>
        </defs>

        <g filter="url(#shadow)">
          <rect x="{rect_x}" y="{rect_y}" width="{rect_w}" height="{rect_h}"
                fill="url(#bodyGrad)" stroke="#4d6f89" stroke-width="2"/>
          <ellipse cx="{rect_x + rect_w}" cy="{y0}" rx="{rx}" ry="{ry}"
                   fill="#82a9cb" stroke="#4d6f89" stroke-width="2"/>
          <ellipse cx="{x0 + rx}" cy="{y0}" rx="{rx}" ry="{ry}"
                   fill="url(#faceGrad)" stroke="#4d6f89" stroke-width="2"/>
        </g>

        <ellipse cx="{x0 + rx}" cy="{y0 - ry*0.12}" rx="{rx*0.82}" ry="{ry*0.56}"
                 fill="rgba(255,255,255,0.40)" />
        <ellipse cx="{rect_x + rect_w}" cy="{y0 - ry*0.10}" rx="{rx*0.72}" ry="{ry*0.46}"
                 fill="rgba(255,255,255,0.18)" />

        <!-- cota do diâmetro -->
        <line x1="{dim_x}" y1="{y1}" x2="{dim_x}" y2="{y2}"
              stroke="#111" stroke-width="2"
              marker-start="url(#arrow)" marker-end="url(#arrow)" />
        <line x1="{dim_x+12}" y1="{y1}" x2="{x0+6}" y2="{y1}" stroke="#111" stroke-width="1.6"/>
        <line x1="{dim_x+12}" y1="{y2}" x2="{x0+6}" y2="{y2}" stroke="#111" stroke-width="1.6"/>
        <text x="{dim_x-10}" y="{(y1+y2)/2}" font-family="Arial, sans-serif" font-size="24"
              text-anchor="middle" dominant-baseline="middle"
              transform="rotate(-90 {dim_x-10} {(y1+y2)/2})">D = {d_mm:.1f} mm</text>

        <!-- cota do comprimento -->
        <line x1="{x1}" y1="{len_y}" x2="{x2}" y2="{len_y}"
              stroke="#111" stroke-width="2"
              marker-start="url(#arrow)" marker-end="url(#arrow)" />
        <line x1="{x1}" y1="{rect_y + rect_h + 10}" x2="{x1}" y2="{len_y - 10}" stroke="#111" stroke-width="1.6"/>
        <line x1="{x2}" y1="{rect_y + rect_h + 10}" x2="{x2}" y2="{len_y - 10}" stroke="#111" stroke-width="1.6"/>
        <text x="{(x1+x2)/2}" y="{len_y + 34}" font-family="Arial, sans-serif" font-size="26"
              text-anchor="middle">L = {l_mm:.1f} mm</text>
      </svg>
    </div>
    """


def show_basic_table(values, symbol):
    rows = []
    for i, v in enumerate(values, 1):
        rows.append([str(i), fixed_str(v, 2)])
    rows.append(["n = 5", "—"])
    html = html_table(["Medição", f"{symbol}i (mm)"], rows)
    st.markdown(html, unsafe_allow_html=True)


def show_full_table(values, mean, devs, squares, symbol):
    rows = []
    for i, (v, d, s) in enumerate(zip(values, devs, squares), 1):
        rows.append(
            [
                str(i),
                fixed_str(v, 2),
                plain_str_limited(d, 12),
                plain_str_limited(s, 12),
            ]
        )
    rows.append(
        [
            "n = 5",
            f"{symbol}m = {plain_str_limited(mean, 12)}",
            "—",
            "—",
        ]
    )
    html = html_table(
        [
            "Medição",
            f"{symbol}i (mm)",
            f"({symbol}i - {symbol}m) (mm)",
            f"({symbol}i - {symbol}m)² (mm²)",
        ],
        rows,
    )
    st.markdown(html, unsafe_allow_html=True)


def show_rounding_rules():
    st.markdown(
        """
        <div class="highlight">
        <b>Regras de arredondamento utilizadas</b><br><br>
        (i) após o último algarismo a ser preservado (UAP), se houver um número maior ou igual a 6, 
        ou o número 5 que tenha números diferentes de zero depois dele: somar 1 ao UAP;<br>
        (ii) após o UAP, se houver um número menor que 5: manter o UAP;<br>
        (iii) após o UAP, se houver um número 5, ou 5 seguido apenas de zeros: somar 1 ao UAP se o UAP for ímpar; 
        se o UAP for par, manter o UAP como está.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# ESTADO
# ============================================================
if "seed_D" not in st.session_state:
    st.session_state.seed_D = random.randint(0, 10_000_000)

if "seed_L" not in st.session_state:
    st.session_state.seed_L = random.randint(0, 10_000_000)

# ============================================================
# A. INÍCIO
# ============================================================
col1, col2 = st.columns([1, 3], vertical_alignment="center")
with col1:
    logo_path = Path("logo_maua.png")
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
    else:
        st.warning("Arquivo logo_maua.png não encontrado na raiz do repositório.")

with col2:
    st.title("Prática Propagação de Incerteza")
    st.markdown(
        r"""
Pratique como informar o resultado final do volume \(V\) de um cilindro, incluindo sua incerteza, 
considerando medições com paquímetro de resolução \(\sigma_{instr} = \pm 0{,}05\ \text{mm}\).
        """
    )

# ============================================================
# B. PARÂMETROS
# ============================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Parâmetros")

colp1, colp2 = st.columns(2)
with colp1:
    D_slider = st.slider(
        "Diâmetro aproximado do cilindro D (mm)",
        min_value=0.1,
        max_value=100.0,
        value=20.0,
        step=0.1,
        format="%.1f",
    )
with colp2:
    L_slider = st.slider(
        "Comprimento aproximado do cilindro L (mm)",
        min_value=0.1,
        max_value=200.0,
        value=50.0,
        step=0.1,
        format="%.1f",
    )

D_approx = Decimal(f"{D_slider:.1f}")
L_approx = Decimal(f"{L_slider:.1f}")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# C. IMAGEM
# ============================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Imagem")
st.caption("Arraste horizontalmente no celular para visualizar a figura inteira. A escala da imagem é fixa.")
svg = cylinder_svg(float(D_slider), float(L_slider))
components.html(svg, height=470, scrolling=False)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# GERAÇÃO DAS MEDIÇÕES
# ============================================================
control_col1, control_col2 = st.columns(2)
with control_col1:
    if st.button("Gerar novos valores aleatórios para D", use_container_width=True):
        st.session_state.seed_D = random.randint(0, 10_000_000)
with control_col2:
    if st.button("Gerar novos valores aleatórios para L", use_container_width=True):
        st.session_state.seed_L = random.randint(0, 10_000_000)

D_values = generate_measurements(D_approx, "seed_D")
L_values = generate_measurements(L_approx, "seed_L")

Dm, D_devs, D_squares, D_sum_sq, sigma_est_D = calc_stats(D_values)
Lm, L_devs, L_squares, L_sum_sq, sigma_est_L = calc_stats(L_values)

sigma_est_D_round = round_uncertainty(sigma_est_D)
sigma_est_L_round = round_uncertainty(sigma_est_L)

sigma_comb_D_raw = calc_combined(sigma_est_D_round, SIGMA_INSTR)
sigma_comb_L_raw = calc_combined(sigma_est_L_round, SIGMA_INSTR)

sigma_comb_D = round_uncertainty(sigma_comb_D_raw)
sigma_comb_L = round_uncertainty(sigma_comb_L_raw)

D_result = round_value_to_match_uncertainty(Dm, sigma_comb_D)
L_result = round_value_to_match_uncertainty(Lm, sigma_comb_L)

V_raw = (Decimal(str(math.pi)) * (Dm ** 2) / Decimal("4")) * Lm
# propagação: V = C * D^2 * L
sigma_V_raw = abs(V_raw) * sqrt_decimal(
    (Decimal("2") * sigma_comb_D / Dm) ** 2
    + (Decimal("1") * sigma_comb_L / Lm) ** 2
)
sigma_V = round_uncertainty(sigma_V_raw)
V_result = round_value_to_match_uncertainty(V_raw, sigma_V)

# ============================================================
# L. VISIBILIDADE INICIAL
# Mostrar inicialmente apenas os números aleatórios criados para D e L.
# Os demais resultados ficam em expanders (cliques).
# ============================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Valores aleatórios gerados (visíveis inicialmente)")

col_init1, col_init2 = st.columns(2)
with col_init1:
    st.subheader("Diâmetro")
    show_basic_table(D_values, "D")

with col_init2:
    st.subheader("Comprimento")
    show_basic_table(L_values, "L")

st.markdown(
    '<p class="small-note">Os demais resultados aparecem ao abrir as seções abaixo.</p>',
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# D. INCERTEZA INSTRUMENTAL
# ============================================================
with st.expander("D. Incerteza instrumental", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        r"""
Para instrumento de medição com nônio, a incerteza instrumental \(\sigma_{instr}\) equivale à resolução.
        """
    )
    st.markdown(
        r"""
<div class="math-box">
\[
\sigma_{instr} = \pm 0{,}05\ \text{mm}
\]
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# E. INCERTEZA ESTATÍSTICA
# ============================================================
with st.expander("E. Incerteza estatística", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Incerteza estatística")

    tabs = st.tabs(["Diâmetro D", "Comprimento L"])

    with tabs[0]:
        st.subheader("Tabela completa para o diâmetro")
        show_full_table(D_values, Dm, D_devs, D_squares, "D")

        st.markdown(
            r"""
<div class="math-box">
\[
\sigma_{est} = \sqrt{\frac{\sum (D_i - D_m)^2}{n(n-1)}}
\]
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            rf"""
<div class="math-box">
\[
\sigma_{{est}} =
\sqrt{{\frac{{{plain_str_limited(D_sum_sq, 12)}}}{{5\cdot 4}}}}
\]
</div>
            """,
            unsafe_allow_html=True,
        )

        st.write(f"Resultado sem arredondamento: σ_est = {plain_str_limited(sigma_est_D, 12)} mm")

        st.markdown(
            """
**Regra para arredondar a incerteza estatística:** informar com **1 algarismo significativo (AS)**, 
exceto se o primeiro AS for **1** ou **2**; nesse caso, informar **2 AS**.
            """
        )
        st.write(f"Resultado arredondado: σ_est = {plain_str(sigma_est_D_round)} mm")

    with tabs[1]:
        st.subheader("Tabela completa para o comprimento")
        show_full_table(L_values, Lm, L_devs, L_squares, "L")

        st.markdown(
            r"""
<div class="math-box">
\[
\sigma_{est} = \sqrt{\frac{\sum (L_i - L_m)^2}{n(n-1)}}
\]
</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            rf"""
<div class="math-box">
\[
\sigma_{{est}} =
\sqrt{{\frac{{{plain_str_limited(L_sum_sq, 12)}}}{{5\cdot 4}}}}
\]
</div>
            """,
            unsafe_allow_html=True,
        )

        st.write(f"Resultado sem arredondamento: σ_est = {plain_str_limited(sigma_est_L, 12)} mm")

        st.markdown(
            """
**Regra para arredondar a incerteza estatística:** informar com **1 algarismo significativo (AS)**, 
exceto se o primeiro AS for **1** ou **2**; nesse caso, informar **2 AS**.
            """
        )
        st.write(f"Resultado arredondado: σ_est = {plain_str(sigma_est_L_round)} mm")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# F. INCERTEZA COMBINADA
# ============================================================
with st.expander("F. Incerteza combinada", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Incerteza combinada")

    tabs = st.tabs(["Diâmetro D", "Comprimento L"])

    with tabs[0]:
        st.markdown(
            r"""
<div class="math-box">
\[
\sigma_{comb} = \sqrt{\sigma_{est}^2 + \sigma_{instr}^2}
\]
</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            rf"""
<div class="math-box">
\[
\sigma_{{comb}} = \sqrt{{({plain_str(sigma_est_D_round)})^2 + (0.05)^2}}
\]
</div>
            """,
            unsafe_allow_html=True,
        )
        st.write(f"Resultado sem arredondamento: σ_comb = {plain_str_limited(sigma_comb_D_raw, 12)} mm")
        st.write(f"Resultado final arredondado: σ_comb = {plain_str(sigma_comb_D)} mm")
        st.info(
            "Como a incerteza instrumental tem apenas um algarismo significativo, "
            "a incerteza combinada fica limitada a ter apenas um algarismo significativo."
        )

    with tabs[1]:
        st.markdown(
            r"""
<div class="math-box">
\[
\sigma_{comb} = \sqrt{\sigma_{est}^2 + \sigma_{instr}^2}
\]
</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            rf"""
<div class="math-box">
\[
\sigma_{{comb}} = \sqrt{{({plain_str(sigma_est_L_round)})^2 + (0.05)^2}}
\]
</div>
            """,
            unsafe_allow_html=True,
        )
        st.write(f"Resultado sem arredondamento: σ_comb = {plain_str_limited(sigma_comb_L_raw, 12)} mm")
        st.write(f"Resultado final arredondado: σ_comb = {plain_str(sigma_comb_L)} mm")
        st.info(
            "Como a incerteza instrumental tem apenas um algarismo significativo, "
            "a incerteza combinada fica limitada a ter apenas um algarismo significativo."
        )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# G. RESULTADO DAS MEDIÇÕES
# ============================================================
with st.expander("G. Resultado das medições", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Resultado das medições")

    colg1, colg2 = st.columns(2)
    with colg1:
        st.markdown(
            f"""
<div class="result-box">
<b>Diâmetro final</b><br><br>
D = {plain_str(D_result)} ± {plain_str(sigma_comb_D)} mm
</div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("O valor médio foi arredondado para ter o mesmo número de casas decimais da incerteza combinada.")

    with colg2:
        st.markdown(
            f"""
<div class="result-box">
<b>Comprimento final</b><br><br>
L = {plain_str(L_result)} ± {plain_str(sigma_comb_L)} mm
</div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("O valor médio foi arredondado para ter o mesmo número de casas decimais da incerteza combinada.")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# H. VOLUME
# ============================================================
with st.expander("H. Volume", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Volume")
    st.markdown(
        r"""
Volume \(V\) de um cilindro equivale ao produto entre a área da seção transversal (circular) pelo comprimento do cilindro.
        """
    )

    st.markdown(
        r"""
<div class="math-box">
\[
V = \left(\frac{\pi D_m^2}{4}\right)L_m
\]
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        rf"""
<div class="math-box">
\[
V = \left(\frac{{\pi \cdot ({plain_str_limited(Dm, 12)})^2}}{{4}}\right)\cdot {plain_str_limited(Lm, 12)}
\]
</div>
        """,
        unsafe_allow_html=True,
    )

    st.write(f"Resultado sem arredondamento: V = {plain_str_limited(V_raw, 12)} mm³")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# I. INCERTEZA DO VOLUME
# ============================================================
with st.expander("I. Incerteza do volume", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Incerteza do volume")

    st.markdown(
        r"""
Como o volume foi calculado a partir de medições com incertezas, é necessário aplicar o conceito de propagação de incerteza.  
No caso de produto entre duas medições, considerando também o expoente de cada grandeza:
        """
    )

    st.markdown(
        r"""
<div class="math-box">
\[
\sigma_V =
V\sqrt{
\left(\frac{\sigma_D \cdot 2}{D}\right)^2 +
\left(\frac{\sigma_L \cdot 1}{L}\right)^2
}
\]
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        rf"""
<div class="math-box">
\[
\sigma_V =
{plain_str_limited(V_raw, 12)}
\sqrt{{
\left(\frac{{{plain_str(sigma_comb_D)}\cdot 2}}{{{plain_str_limited(Dm, 12)}}}\right)^2 +
\left(\frac{{{plain_str(sigma_comb_L)}\cdot 1}}{{{plain_str_limited(Lm, 12)}}}\right)^2
}}
\]
</div>
        """,
        unsafe_allow_html=True,
    )

    st.write(f"Resultado sem arredondamento: σ_V = {plain_str_limited(sigma_V_raw, 12)} mm³")
    st.write(f"Resultado arredondado: σ_V = {plain_str(sigma_V)} mm³")
    st.info(
        "Como as incertezas anteriores têm apenas um algarismo significativo, "
        "a incerteza final fica limitada a ter apenas um algarismo significativo."
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# J. RESULTADO FINAL
# ============================================================
with st.expander("J. Resultado final", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Resultado final")
    st.markdown(
        f"""
<div class="result-box" style="font-size:1.15rem;">
<b>V = {plain_str(V_result)} ± {plain_str(sigma_V)} mm³</b>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("O valor do volume foi arredondado para ter o mesmo número de casas decimais da incerteza.")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# K. REGRAS DE ARREDONDAMENTO
# ============================================================
with st.expander("K. Regras de arredondamento", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Regras de arredondamento")
    show_rounding_rules()
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# RODAPÉ
# ============================================================
st.markdown(
    """
    <p class="foot">
    Dica de uso em aula: peça ao estudante que abra cada seção em sequência e tente prever o próximo passo do cálculo antes de visualizar a resposta.
    </p>
    """,
    unsafe_allow_html=True,
)
