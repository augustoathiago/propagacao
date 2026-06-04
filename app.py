import math
import random
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Prática Propagação de Incerteza",
    layout="wide",
    initial_sidebar_state="collapsed",
)

getcontext().prec = 60

SIGMA_INSTR = Decimal("0.05")  # mm

# ============================================================
# CSS / ESTILO
# ============================================================
st.markdown(
    """
    <style>
        .main {
            padding-top: 1rem;
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        .section-card {
            padding: 1rem 1.1rem;
            border: 1px solid #d7dde5;
            border-radius: 14px;
            background: #ffffff;
            margin-bottom: 1rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            color: #111111;
        }

        .result-box {
            padding: 0.95rem 1rem;
            border-radius: 12px;
            border: 1px solid #cfd8e3;
            background: #f5f8fc;
            color: #111111;
            margin-top: 0.5rem;
            margin-bottom: 0.7rem;
        }

        .note-box {
            padding: 0.85rem 1rem;
            border-radius: 12px;
            border: 1px solid #cfd8e3;
            background: #f5f8fc;
            color: #111111 !important;
            margin-top: 0.75rem;
            margin-bottom: 0.3rem;
        }

        .small-note {
            font-size: 0.97rem;
            color: #111111 !important;
            margin: 0;
        }

        .highlight-box {
            background: #fff9eb;
            border: 1px solid #efd79c;
            border-radius: 10px;
            padding: 0.8rem 1rem;
            color: #222222;
            margin-top: 0.5rem;
            margin-bottom: 0.8rem;
        }

        table.custom-table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 0.5rem;
            margin-bottom: 0.9rem;
            font-size: 0.96rem;
            color: #111111;
            background: #ffffff;
        }

        table.custom-table th, table.custom-table td {
            border: 1px solid #d6dbe2;
            padding: 8px 10px;
            text-align: center;
            vertical-align: middle;
            color: #111111;
        }

        table.custom-table th {
            background: #eef4fb;
            color: #111111;
            font-weight: 600;
        }

        [data-testid="stExpander"] {
            background: #ffffff !important;
            border: 1px solid #d7dde5 !important;
            border-radius: 12px !important;
        }

        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary * {
            color: #111111 !important;
            background: #ffffff !important;
        }

        [data-testid="stExpander"] details,
        [data-testid="stExpander"] details * {
            color: #111111 !important;
        }

        .stMarkdown, .stText, p, li, label, span, div {
            color: inherit;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.8rem;
                padding-right: 0.8rem;
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
        raise ValueError("Não é possível calcular raiz quadrada de número negativo.")
    return x.sqrt()


def quant_step(x: Decimal, step: Decimal) -> Decimal:
    """
    Arredonda x para múltiplos de 'step' com half-even.
    Ex.: step = 0,05
    """
    x = dec(x)
    step = dec(step)
    return (x / step).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN) * step


def count_decimal_places_preserved(x: Decimal) -> int:
    """
    Conta casas decimais preservadas no Decimal quantizado.
    Ex.: Decimal('0.10') -> 2
    """
    x = dec(x)
    exponent = x.as_tuple().exponent
    return -exponent if exponent < 0 else 0


def decimal_to_br_fixed(x: Decimal, places: int) -> str:
    x = dec(x)
    q = Decimal(1).scaleb(-places)
    y = x.quantize(q, rounding=ROUND_HALF_EVEN)
    return f"{y:.{places}f}".replace(".", ",")


def decimal_to_br_plain(x: Decimal, max_places: int = 12) -> str:
    x = dec(x)
    q = Decimal(1).scaleb(-max_places)
    y = x.quantize(q, rounding=ROUND_HALF_EVEN)
    s = f"{y:.{max_places}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s.replace(".", ",")


def latex_decimal_plain(x: Decimal, max_places: int = 12) -> str:
    return decimal_to_br_plain(x, max_places=max_places).replace(",", "{,}")


def latex_decimal_fixed(x: Decimal, places: int) -> str:
    return decimal_to_br_fixed(x, places).replace(",", "{,}")


def first_significant_digit(x: Decimal) -> int:
    x = abs(dec(x))
    if x == 0:
        return 0
    n = x.normalize()
    return int(n.as_tuple().digits[0])


def sig_digits_for_uncertainty_general(x: Decimal) -> int:
    """
    Regra geral:
    - 1 AS
    - exceto se o primeiro AS for 1 ou 2, então 2 AS
    """
    fd = first_significant_digit(x)
    return 2 if fd in (1, 2) else 1


def round_sig_half_even(x: Decimal, sig_digits: int) -> Decimal:
    """
    Arredonda para N algarismos significativos usando ROUND_HALF_EVEN.
    """
    x = dec(x)
    if x == 0:
        return Decimal("0")
    exponent = x.adjusted()
    quantum = Decimal(f"1e{exponent - sig_digits + 1}")
    return x.quantize(quantum, rounding=ROUND_HALF_EVEN)


def round_uncertainty_general(x: Decimal) -> Decimal:
    """
    Para sigma_est:
    - 1 AS
    - exceto se o primeiro AS for 1 ou 2, então 2 AS
    """
    x = abs(dec(x))
    if x == 0:
        return Decimal("0")
    return round_sig_half_even(x, sig_digits_for_uncertainty_general(x))


def round_uncertainty_1sig(x: Decimal) -> Decimal:
    """
    Para sigma_comb e sigma_V: sempre 1 AS.
    """
    x = abs(dec(x))
    if x == 0:
        return Decimal("0")
    return round_sig_half_even(x, 1)


def needs_scientific_notation_for_sig(x: Decimal, sig_digits: int) -> bool:
    """
    Evita ambiguidades como 100, 120, 1000 etc.
    """
    x = abs(dec(x))
    if x == 0:
        return False

    exponent = x.adjusted()

    if exponent >= sig_digits:
        return True

    if exponent <= -4:
        return True

    return False


def superscript_int(n: int) -> str:
    mapping = {
        "-": "⁻",
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
    }
    return "".join(mapping[ch] for ch in str(n))


def format_sig_display_br(x: Decimal, sig_digits: int) -> str:
    """
    Exibe número arredondado para N AS.
    Se houver ambiguidade na escrita decimal, usa notação científica:
    1 × 10²
    """
    rounded = round_sig_half_even(dec(x), sig_digits)

    if rounded == 0:
        return "0"

    if needs_scientific_notation_for_sig(rounded, sig_digits):
        exponent = rounded.adjusted()
        mantissa = rounded.scaleb(-exponent)
        mantissa_quant = Decimal(f"1e-{sig_digits-1}") if sig_digits > 1 else Decimal("1")
        mantissa = mantissa.quantize(mantissa_quant, rounding=ROUND_HALF_EVEN)
        mantissa_places = count_decimal_places_preserved(mantissa)
        mantissa_str = decimal_to_br_fixed(mantissa, mantissa_places)
        return f"{mantissa_str} × 10{superscript_int(exponent)}"

    places = count_decimal_places_preserved(rounded)
    return decimal_to_br_fixed(rounded, places)


def format_sig_display_latex(x: Decimal, sig_digits: int) -> str:
    rounded = round_sig_half_even(dec(x), sig_digits)

    if rounded == 0:
        return "0"

    if needs_scientific_notation_for_sig(rounded, sig_digits):
        exponent = rounded.adjusted()
        mantissa = rounded.scaleb(-exponent)
        mantissa_quant = Decimal(f"1e-{sig_digits-1}") if sig_digits > 1 else Decimal("1")
        mantissa = mantissa.quantize(mantissa_quant, rounding=ROUND_HALF_EVEN)
        mantissa_places = count_decimal_places_preserved(mantissa)
        mantissa_str = latex_decimal_fixed(mantissa, mantissa_places)
        return rf"{mantissa_str}\times 10^{{{exponent}}}"

    places = count_decimal_places_preserved(rounded)
    return latex_decimal_fixed(rounded, places)


def round_value_to_match_uncertainty(value: Decimal, uncertainty: Decimal) -> Decimal:
    """
    Arredonda o valor para o mesmo número de casas decimais da incerteza.
    """
    value = dec(value)
    uncertainty = dec(uncertainty)

    if uncertainty == 0:
        return value

    places = count_decimal_places_preserved(uncertainty)
    q = Decimal(1).scaleb(-places)
    return value.quantize(q, rounding=ROUND_HALF_EVEN)


def format_value_matching_uncertainty_br(value: Decimal, uncertainty: Decimal) -> str:
    """
    Exibe o valor com exatamente o mesmo número de casas decimais da incerteza.
    """
    rounded_value = round_value_to_match_uncertainty(value, uncertainty)
    places = count_decimal_places_preserved(uncertainty)
    return decimal_to_br_fixed(rounded_value, places)


def common_scientific_pair_br(value: Decimal, uncertainty: Decimal, uncertainty_sig_digits: int):
    """
    Formata valor e incerteza usando o MESMO expoente científico, tomado da incerteza.
    O valor é arredondado para ter o mesmo número de casas decimais da mantissa da incerteza.
    Retorna:
      value_str, uncertainty_str, exponent
    tal que o usuário pode exibir:
      (value_str ± uncertainty_str) × 10^exponent
    """
    unc_rounded = round_sig_half_even(dec(uncertainty), uncertainty_sig_digits)

    if unc_rounded == 0:
        return decimal_to_br_plain(value), "0", 0

    exponent = unc_rounded.adjusted()

    unc_mantissa = unc_rounded.scaleb(-exponent)
    unc_places = count_decimal_places_preserved(unc_mantissa)

    q = Decimal(1).scaleb(-unc_places)

    value_mantissa = (dec(value) / (Decimal(10) ** exponent)).quantize(q, rounding=ROUND_HALF_EVEN)
    unc_mantissa = unc_mantissa.quantize(q, rounding=ROUND_HALF_EVEN)

    value_str = decimal_to_br_fixed(value_mantissa, unc_places)
    unc_str = decimal_to_br_fixed(unc_mantissa, unc_places)

    return value_str, unc_str, exponent


def html_table(headers, rows):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        trs.append(f"<tr>{tds}</tr>")
    return f"""
    <table class="custom-table">
        <thead><tr>{th}</tr></thead>
        <tbody>{''.join(trs)}</tbody>
    </table>
    """


def generate_measurements(center: Decimal, seed: int):
    """
    Gera 5 medições próximas do valor escolhido, em passos de 0,05 mm.
    """
    center = dec(center)
    rng = random.Random(seed)
    step = Decimal("0.05")

    offsets = [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]

    values = []
    for _ in range(5):
        k = rng.choice(offsets)
        v = center + Decimal(k) * step
        if v < Decimal("1.00"):
            v = Decimal("1.00")
        v = quant_step(v, step)
        values.append(v.quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN))

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


def calc_combined(sigma_est_rounded: Decimal, sigma_instr: Decimal = SIGMA_INSTR) -> Decimal:
    return sqrt_decimal(dec(sigma_est_rounded) ** 2 + dec(sigma_instr) ** 2)


def prepare_logo_with_top_margin(path: str, top_margin_px: int = 60, side_margin_px: int = 12, bottom_margin_px: int = 10):
    """
    Abre o logo e adiciona margem transparente em cima para evitar corte visual.
    """
    file_path = Path(path)
    if not file_path.exists():
        return None

    img = Image.open(file_path).convert("RGBA")

    new_w = img.width + 2 * side_margin_px
    new_h = img.height + top_margin_px + bottom_margin_px

    canvas = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 0))
    canvas.paste(img, (side_margin_px, top_margin_px), img)

    return canvas


def cylinder_svg(d_mm: float, l_mm: float) -> tuple[str, int]:
    """
    Desenha cilindro vertical em SVG.
    """
    body_w = max(220.0, 140.0 + 4.0 * d_mm)
    body_h = max(270.0, 120.0 + 4.4 * l_mm)

    ellipse_rx = body_w / 2.0
    ellipse_ry = max(30.0, ellipse_rx * 0.22)

    margin_left = 95.0
    margin_top = 60.0
    margin_right = 240.0
    margin_bottom = 70.0

    x_center = margin_left + ellipse_rx
    top_y = margin_top + ellipse_ry
    bottom_y = top_y + body_h

    left_x = x_center - ellipse_rx
    right_x = x_center + ellipse_rx

    total_w = int(margin_left + body_w + margin_right)
    total_h = int(margin_top + body_h + 2 * ellipse_ry + margin_bottom + 20)

    d_text = f"D = {d_mm:.2f} mm".replace(".", ",")
    l_text = f"L = {l_mm:.2f} mm".replace(".", ",")

    d_y = top_y - ellipse_ry * 0.12

    dim_x = right_x + 58
    dim_y1 = top_y - ellipse_ry * 0.10
    dim_y2 = bottom_y + ellipse_ry * 0.10

    svg = f"""
    <div style="
        width:100%;
        overflow-x:auto;
        overflow-y:hidden;
        border:1px solid #d6dbe2;
        border-radius:14px;
        background:#ffffff;
        padding:8px;
        -webkit-overflow-scrolling:touch;
        touch-action:pan-x pan-y;
    ">
      <svg
          width="{total_w}"
          height="{total_h}"
          viewBox="0 0 {total_w} {total_h}"
          xmlns="http://www.w3.org/2000/svg"
          style="display:block; max-width:none; user-select:none; background: #ffffff;"
          preserveAspectRatio="xMinYMin meet"
      >
        <defs>
          <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stop-color="#6f70d9"/>
            <stop offset="50%" stop-color="#7778df"/>
            <stop offset="100%" stop-color="#6a6ccc"/>
          </linearGradient>
          <marker id="arrowThin" viewBox="0 0 10 10" refX="5" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#111111"/>
          </marker>
        </defs>

        <rect x="{left_x}" y="{top_y}" width="{body_w}" height="{body_h}"
              fill="url(#bodyGrad)" opacity="0.96"/>

        <line x1="{left_x}" y1="{top_y}" x2="{left_x}" y2="{bottom_y}"
              stroke="#1022ff" stroke-width="3"/>
        <line x1="{right_x}" y1="{top_y}" x2="{right_x}" y2="{bottom_y}"
              stroke="#1022ff" stroke-width="3"/>

        <ellipse cx="{x_center}" cy="{top_y}" rx="{ellipse_rx}" ry="{ellipse_ry}"
                 fill="#8b8ce9" stroke="#1022ff" stroke-width="3"/>

        <path d="M {left_x},{bottom_y}
                 A {ellipse_rx},{ellipse_ry} 0 0 1 {right_x},{bottom_y}"
              fill="none" stroke="#1022ff" stroke-width="3"
              stroke-dasharray="12 10" opacity="0.95"/>

        <path d="M {right_x},{bottom_y}
                 A {ellipse_rx},{ellipse_ry} 0 0 1 {left_x},{bottom_y}"
              fill="none" stroke="#1022ff" stroke-width="3"/>

        <line x1="{left_x}" y1="{d_y}" x2="{right_x}" y2="{d_y}"
              stroke="#111111" stroke-width="3"/>
        <circle cx="{left_x}" cy="{d_y}" r="6" fill="#111111"/>
        <circle cx="{x_center}" cy="{d_y}" r="6" fill="#111111"/>
        <circle cx="{right_x}" cy="{d_y}" r="6" fill="#111111"/>

        <text x="{x_center}" y="{top_y - ellipse_ry - 14}" text-anchor="middle"
              font-size="24" font-family="Arial, sans-serif" fill="#111111">{d_text}</text>

        <text x="{x_center}" y="{d_y + 52}" text-anchor="middle"
              font-size="56" font-family="Times New Roman, serif"
              font-style="italic" fill="#111111">D</text>

        <line x1="{dim_x}" y1="{dim_y1}" x2="{dim_x}" y2="{dim_y2}"
              stroke="#111111" stroke-width="2.8"
              marker-start="url(#arrowThin)" marker-end="url(#arrowThin)"/>
        <line x1="{right_x + 16}" y1="{dim_y1}" x2="{dim_x - 10}" y2="{dim_y1}"
              stroke="#111111" stroke-width="2"/>
        <line x1="{right_x + 16}" y1="{dim_y2}" x2="{dim_x - 10}" y2="{dim_y2}"
              stroke="#111111" stroke-width="2"/>

        <text x="{dim_x + 28}" y="{(dim_y1 + dim_y2)/2 - 8}" text-anchor="start"
              font-size="58" font-family="Times New Roman, serif"
              font-style="italic" fill="#111111">L</text>

        <text x="{dim_x + 28}" y="{(dim_y1 + dim_y2)/2 + 28}" text-anchor="start"
              font-size="22" font-family="Arial, sans-serif" fill="#111111">{l_text}</text>
      </svg>
    </div>
    """

    return svg, total_h + 20


def show_basic_table(values, symbol):
    rows = []
    for i, v in enumerate(values, start=1):
        rows.append([str(i), decimal_to_br_fixed(v, 2)])
    rows.append(["n = 5", "—"])
    st.markdown(
        html_table(
            ["Medição", f"{symbol}i (mm)"],
            rows,
        ),
        unsafe_allow_html=True,
    )


def show_full_table(values, mean, deviations, squares, symbol):
    rows = []
    for i, (v, d, s) in enumerate(zip(values, deviations, squares), start=1):
        rows.append([
            str(i),
            decimal_to_br_fixed(v, 2),
            decimal_to_br_plain(d, 12),
            decimal_to_br_plain(s, 12),
        ])
    rows.append([
        "n = 5",
        f"{symbol}m = {decimal_to_br_plain(mean, 12)}",
        "—",
        "—",
    ])
    st.markdown(
        html_table(
            ["Medição", f"{symbol}i (mm)", f"({symbol}i - {symbol}m) (mm)", f"({symbol}i - {symbol}m)² (mm²)"],
            rows,
        ),
        unsafe_allow_html=True,
    )


def uncertainty_html_label(base: str, sub: str) -> str:
    return f"{base}<sub>{sub}</sub>"


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
col_logo, col_title = st.columns([1, 3], vertical_alignment="center")

with col_logo:
    logo = prepare_logo_with_top_margin("logo_maua.png", top_margin_px=100, side_margin_px=100, bottom_margin_px=100)
    if logo is not None:
        st.image(logo, width=260)
    else:
        st.warning("Arquivo logo_maua.png não encontrado.")

with col_title:
    st.title("Prática Propagação de Incerteza")
    st.write(
        "Pratique como informar o resultado final do volume "
        r"$V$ de um cilindro, incluindo sua incerteza, considerando medições "
        r"com paquímetro de resolução 0,05 mm."
    )

# ============================================================
# B. PARÂMETROS
# ============================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Parâmetros")

col_p1, col_p2 = st.columns(2)

with col_p1:
    D_slider = st.slider(
        "Diâmetro aproximado do cilindro D (mm)",
        min_value=1.00,
        max_value=100.00,
        value=20.00,
        step=0.01,
        format="%.2f",
    )

with col_p2:
    L_slider = st.slider(
        "Comprimento aproximado do cilindro L (mm)",
        min_value=1.00,
        max_value=200.00,
        value=50.00,
        step=0.01,
        format="%.2f",
    )

D_approx = Decimal(f"{D_slider:.2f}")
L_approx = Decimal(f"{L_slider:.2f}")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# C. IMAGEM
# ============================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Imagem")
st.caption("Em celular, arraste horizontalmente para observar toda a figura. O zoom permanece fixo.")
svg_html, svg_height = cylinder_svg(float(D_slider), float(L_slider))
components.html(svg_html, height=svg_height, scrolling=False)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# GERAÇÃO DOS DADOS
# ============================================================
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("Gerar novos valores aleatórios para D", use_container_width=True):
        st.session_state.seed_D = random.randint(0, 10_000_000)

with col_btn2:
    if st.button("Gerar novos valores aleatórios para L", use_container_width=True):
        st.session_state.seed_L = random.randint(0, 10_000_000)

D_values = generate_measurements(D_approx, st.session_state.seed_D)
L_values = generate_measurements(L_approx, st.session_state.seed_L)

Dm, D_devs, D_squares, D_sum_sq, sigma_est_D = calc_stats(D_values)
Lm, L_devs, L_squares, L_sum_sq, sigma_est_L = calc_stats(L_values)

# sigma_est arredondada com regra geral
sigma_est_D_round = round_uncertainty_general(sigma_est_D)
sigma_est_L_round = round_uncertainty_general(sigma_est_L)

# sigma_comb calculada com sigma_est arredondada
sigma_comb_D_raw = calc_combined(sigma_est_D_round, SIGMA_INSTR)
sigma_comb_L_raw = calc_combined(sigma_est_L_round, SIGMA_INSTR)

# sigma_comb final arredondada com 1 AS
sigma_comb_D = round_uncertainty_1sig(sigma_comb_D_raw)
sigma_comb_L = round_uncertainty_1sig(sigma_comb_L_raw)

D_result = round_value_to_match_uncertainty(Dm, sigma_comb_D)
L_result = round_value_to_match_uncertainty(Lm, sigma_comb_L)

PI_DEC = Decimal(str(math.pi))
V_raw = (PI_DEC * (Dm ** 2) / Decimal("4")) * Lm

sigma_V_raw = abs(V_raw) * sqrt_decimal(
    (Decimal("2") * sigma_comb_D / Dm) ** 2 +
    (sigma_comb_L / Lm) ** 2
)

sigma_V = round_uncertainty_1sig(sigma_V_raw)
V_result = round_value_to_match_uncertainty(V_raw, sigma_V)

# ============================================================
# VISIBILIDADE INICIAL
# ============================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.header("Valores aleatórios gerados")

col_init1, col_init2 = st.columns(2)

with col_init1:
    st.subheader("Diâmetro")
    show_basic_table(D_values, "D")

with col_init2:
    st.subheader("Comprimento")
    show_basic_table(L_values, "L")

st.markdown(
    """
    <div class="note-box">
        <p class="small-note">Abra as seções abaixo para visualizar o passo a passo dos cálculos.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# D. INCERTEZA INSTRUMENTAL
# ============================================================
with st.expander("D. Incerteza instrumental", expanded=False):
    st.write(
        "Para instrumento de medição com nônio, a incerteza instrumental "
        r"$\sigma_{instr}$ equivale à resolução."
    )
    st.latex(r"\sigma_{instr} = \pm 0{,}05\ \mathrm{mm}")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# E. INCERTEZA ESTATÍSTICA
# ============================================================
with st.expander("E. Incerteza estatística", expanded=False):
    st.header("Incerteza estatística")

    tab_D, tab_L = st.tabs(["Diâmetro D", "Comprimento L"])

    with tab_D:
        st.subheader("Tabela completa do diâmetro")
        show_full_table(D_values, Dm, D_devs, D_squares, "D")

        st.write("Equação da incerteza estatística:")
        st.latex(r"\sigma_{est} = \sqrt{\frac{\sum (D_i - D_m)^2}{n(n-1)}}")

        st.write("Substituindo os valores:")
        st.latex(
            rf"\sigma_{{est}} = \sqrt{{\frac{{{latex_decimal_plain(D_sum_sq, 12)}}}{{5\cdot 4}}}}"
        )

        st.markdown(
            f"Resultado sem arredondamento: {uncertainty_html_label('σ', 'est')} = "
            f"{decimal_to_br_plain(sigma_est_D, 12)} mm",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="highlight-box">
            A incerteza estatística é informada com <b>1 algarismo significativo</b>, exceto quando o
            primeiro algarismo significativo é <b>1</b> ou <b>2</b>; nesse caso, informam-se <b>2 algarismos significativos</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"Resultado arredondado: {uncertainty_html_label('σ', 'est')} = "
            f"{format_sig_display_br(sigma_est_D, sig_digits_for_uncertainty_general(sigma_est_D))} mm",
            unsafe_allow_html=True,
        )

    with tab_L:
        st.subheader("Tabela completa do comprimento")
        show_full_table(L_values, Lm, L_devs, L_squares, "L")

        st.write("Equação da incerteza estatística:")
        st.latex(r"\sigma_{est} = \sqrt{\frac{\sum (L_i - L_m)^2}{n(n-1)}}")

        st.write("Substituindo os valores:")
        st.latex(
            rf"\sigma_{{est}} = \sqrt{{\frac{{{latex_decimal_plain(L_sum_sq, 12)}}}{{5\cdot 4}}}}"
        )

        st.markdown(
            f"Resultado sem arredondamento: {uncertainty_html_label('σ', 'est')} = "
            f"{decimal_to_br_plain(sigma_est_L, 12)} mm",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="highlight-box">
            A incerteza estatística é informada com <b>1 algarismo significativo</b>, exceto quando o
            primeiro algarismo significativo é <b>1</b> ou <b>2</b>; nesse caso, informam-se <b>2 algarismos significativos</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"Resultado arredondado: {uncertainty_html_label('σ', 'est')} = "
            f"{format_sig_display_br(sigma_est_L, sig_digits_for_uncertainty_general(sigma_est_L))} mm",
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# F. INCERTEZA COMBINADA
# ============================================================
with st.expander("F. Incerteza combinada", expanded=False):
    st.header("Incerteza combinada")

    tab_Dc, tab_Lc = st.tabs(["Diâmetro D", "Comprimento L"])

    with tab_Dc:
        st.write("Equação da incerteza combinada:")
        st.latex(r"\sigma_{comb} = \sqrt{\sigma_{est}^{2} + \sigma_{instr}^{2}}")

        st.write("Substituindo os valores arredondados de σ_est:")
        st.latex(
            rf"\sigma_{{comb}} = \sqrt{{\left({format_sig_display_latex(sigma_est_D, sig_digits_for_uncertainty_general(sigma_est_D))}\right)^2 + \left(0{{,}}05\right)^2}}"
        )

        st.markdown(
            f"Resultado sem arredondamento: {uncertainty_html_label('σ', 'comb')} = "
            f"{decimal_to_br_plain(sigma_comb_D_raw, 12)} mm",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"Resultado final arredondado: {uncertainty_html_label('σ', 'comb')} = "
            f"{format_sig_display_br(sigma_comb_D_raw, 1)} mm",
            unsafe_allow_html=True,
        )

        st.info(
            "Como a incerteza instrumental tem apenas um algarismo significativo, "
            "a incerteza combinada fica limitada a ter apenas um algarismo significativo."
        )

    with tab_Lc:
        st.write("Equação da incerteza combinada:")
        st.latex(r"\sigma_{comb} = \sqrt{\sigma_{est}^{2} + \sigma_{instr}^{2}}")

        st.write("Substituindo os valores arredondados de σ_est:")
        st.latex(
            rf"\sigma_{{comb}} = \sqrt{{\left({format_sig_display_latex(sigma_est_L, sig_digits_for_uncertainty_general(sigma_est_L))}\right)^2 + \left(0{{,}}05\right)^2}}"
        )

        st.markdown(
            f"Resultado sem arredondamento: {uncertainty_html_label('σ', 'comb')} = "
            f"{decimal_to_br_plain(sigma_comb_L_raw, 12)} mm",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"Resultado final arredondado: {uncertainty_html_label('σ', 'comb')} = "
            f"{format_sig_display_br(sigma_comb_L_raw, 1)} mm",
            unsafe_allow_html=True,
        )

        st.info(
            "Como a incerteza instrumental tem apenas um algarismo significativo, "
            "a incerteza combinada fica limitada a ter apenas um algarismo significativo."
        )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# G. RESULTADO DAS MEDIÇÕES
# ============================================================
with st.expander("G. Resultado das medições", expanded=False):
    st.header("Resultado das medições")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        sigma_D_places = count_decimal_places_preserved(sigma_comb_D)
        sigma_D_display = (
            format_sig_display_br(sigma_comb_D, 1)
            if needs_scientific_notation_for_sig(sigma_comb_D, 1)
            else decimal_to_br_fixed(sigma_comb_D, sigma_D_places)
        )
        D_display = format_value_matching_uncertainty_br(Dm, sigma_comb_D)

        st.markdown(
            f"""
            <div class="result-box">
            <b>Diâmetro final</b><br><br>
            D = {D_display} ± {sigma_D_display} mm
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("O valor médio deve ter o mesmo número de casas decimais da incerteza.")

    with col_g2:
        sigma_L_places = count_decimal_places_preserved(sigma_comb_L)
        sigma_L_display = (
            format_sig_display_br(sigma_comb_L, 1)
            if needs_scientific_notation_for_sig(sigma_comb_L, 1)
            else decimal_to_br_fixed(sigma_comb_L, sigma_L_places)
        )
        L_display = format_value_matching_uncertainty_br(Lm, sigma_comb_L)

        st.markdown(
            f"""
            <div class="result-box">
            <b>Comprimento final</b><br><br>
            L = {L_display} ± {sigma_L_display} mm
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# H. VOLUME
# ============================================================
with st.expander("H. Volume", expanded=False):
    st.header("Volume")

    st.write(
        "Volume $V$ de um cilindro equivale ao produto entre a área da seção "
        "transversal (circular) pelo comprimento do cilindro."
    )

    st.latex(r"V = \left(\frac{\pi D_m^{2}}{4}\right)L_m")

    st.write("Substituindo os valores médios não arredondados:")
    st.latex(
        rf"V = \left(\frac{{\pi\left({latex_decimal_plain(Dm, 12)}\right)^2}}{{4}}\right)\left({latex_decimal_plain(Lm, 12)}\right)"
    )

    st.write(f"Resultado sem arredondamento: V = {decimal_to_br_plain(V_raw, 12)} mm³")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# I. INCERTEZA DO VOLUME
# ============================================================
with st.expander("I. Incerteza do volume", expanded=False):
    st.header("Incerteza do volume")

    st.write(
        "Como o volume foi calculado a partir de medições com incertezas, "
        "é necessário aplicar o conceito de propagação de incerteza."
    )

    st.write(
        "No caso de um produto, considerando os expoentes de "
        r"$D_m$ e $L_m$ na expressão do volume:"
    )

    st.latex(
        r"\sigma_{V} = V\sqrt{\left(\frac{\sigma_{D}\cdot \text{expoente de }D_m}{D_m}\right)^2 + \left(\frac{\sigma_{L}\cdot \text{expoente de }L_m}{L_m}\right)^2}"
    )

    st.write("Como, no volume do cilindro, o expoente de $D_m$ é 2 e o expoente de $L_m$ é 1:")
    st.latex(
        r"\sigma_{V} = V\sqrt{\left(\frac{2\sigma_{D}}{D_m}\right)^2 + \left(\frac{1\sigma_{L}}{L_m}\right)^2}"
    )

    sigma_D_for_eq = (
        format_sig_display_latex(sigma_comb_D, 1)
        if needs_scientific_notation_for_sig(sigma_comb_D, 1)
        else latex_decimal_fixed(sigma_comb_D, count_decimal_places_preserved(sigma_comb_D))
    )
    sigma_L_for_eq = (
        format_sig_display_latex(sigma_comb_L, 1)
        if needs_scientific_notation_for_sig(sigma_comb_L, 1)
        else latex_decimal_fixed(sigma_comb_L, count_decimal_places_preserved(sigma_comb_L))
    )

    st.write("Substituindo os valores:")
    st.latex(
        rf"\sigma_{{V}} = {latex_decimal_plain(V_raw, 12)}\sqrt{{\left(\frac{{2\cdot {sigma_D_for_eq}}}{{{latex_decimal_plain(Dm, 12)}}}\right)^2 + \left(\frac{{1\cdot {sigma_L_for_eq}}}{{{latex_decimal_plain(Lm, 12)}}}\right)^2}}"
    )

    st.markdown(
        f"Resultado sem arredondamento: {uncertainty_html_label('σ', 'V')} = "
        f"{decimal_to_br_plain(sigma_V_raw, 12)} mm³",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"Resultado arredondado: {uncertainty_html_label('σ', 'V')} = "
        f"{format_sig_display_br(sigma_V_raw, 1)} mm³",
        unsafe_allow_html=True,
    )

    st.info(
        "Como as incertezas anteriores têm apenas um algarismo significativo, "
        "a incerteza final fica limitada a ter apenas um algarismo significativo."
    )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# J. RESULTADO FINAL
# ============================================================
with st.expander("J. Resultado final", expanded=False):
    st.header("Resultado final")

    sigma_V_sig_digits = 1
    sigma_V_is_scientific = needs_scientific_notation_for_sig(sigma_V, sigma_V_sig_digits)

    if sigma_V_is_scientific:
        value_mantissa_str, unc_mantissa_str, common_exp = common_scientific_pair_br(
            V_raw, sigma_V, sigma_V_sig_digits
        )

        result_text = (
            f"V = ({value_mantissa_str} ± {unc_mantissa_str}) × 10{superscript_int(common_exp)} mm³"
        )
    else:
        sigma_V_places = count_decimal_places_preserved(sigma_V)
        sigma_V_display = decimal_to_br_fixed(sigma_V, sigma_V_places)
        V_display = format_value_matching_uncertainty_br(V_raw, sigma_V)
        result_text = f"V = {V_display} ± {sigma_V_display} mm³"

    st.markdown(
        f"""
        <div class="result-box" style="font-size:1.15rem;">
        <b>{result_text}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)
