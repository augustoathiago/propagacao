import math
import random
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# CONFIGURAÇÃO GERAL
# ============================================================
st.set_page_config(
    page_title="Prática Propagação de Incerteza",
    layout="wide",
    initial_sidebar_state="collapsed",
)

getcontext().prec = 60

SIGMA_INSTR = Decimal("0.05")  # mm

# ============================================================
# ESTILO
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
            padding: 1rem 1.15rem;
            border: 1px solid #d4d9df;
            border-radius: 14px;
            background: #ffffff;
            margin-bottom: 1rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        }

        .result-box {
            padding: 0.95rem 1rem;
            border-radius: 12px;
            border: 1px solid #ccd4de;
            background: #f5f8fc;
            margin-top: 0.5rem;
            margin-bottom: 0.7rem;
            color: #111111;
        }

        .small-note {
            font-size: 0.95rem;
            color: #333333;
        }

        .foot {
            font-size: 0.92rem;
            color: #333333;
        }

        .math-note {
            background: #f4f8ff;
            border-left: 4px solid #3f78b5;
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
            color: #111111;
            margin-top: 0.5rem;
            margin-bottom: 0.7rem;
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
        }

        table.custom-table th, table.custom-table td {
            border: 1px solid #d6dbe2;
            padding: 8px 10px;
            text-align: center;
            vertical-align: middle;
        }

        table.custom-table th {
            background: #eef4fb;
            color: #111111;
            font-weight: 600;
        }

        .dark-text {
            color: #111111 !important;
        }

        .formula-caption {
            color: #222222;
            font-size: 0.97rem;
            margin-bottom: 0.2rem;
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
    """Converte para Decimal preservando precisão de representação textual."""
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def sqrt_decimal(x: Decimal) -> Decimal:
    x = dec(x)
    if x < 0:
        raise ValueError("Não é possível calcular raiz de número negativo.")
    return x.sqrt()


def quant_step(x: Decimal, step: Decimal) -> Decimal:
    """
    Quantiza x para múltiplos de 'step' usando arredondamento half-even.
    Ex.: step=0.05
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
    exp = x.as_tuple().exponent
    return -exp if exp < 0 else 0


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
    """
    Formato para LaTeX com vírgula decimal.
    """
    return decimal_to_br_plain(x, max_places=max_places).replace(",", "{,}")


def latex_decimal_fixed(x: Decimal, places: int) -> str:
    return decimal_to_br_fixed(x, places).replace(",", "{,}")


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
    Arredonda para N algarismos significativos usando ROUND_HALF_EVEN
    (regra do 5 para o algarismo par).
    """
    x = dec(x)
    if x == 0:
        return Decimal("0")
    exponent = x.adjusted()
    quantum = Decimal(f"1e{exponent - sig_digits + 1}")
    return x.quantize(quantum, rounding=ROUND_HALF_EVEN)


def round_uncertainty(x: Decimal) -> Decimal:
    x = abs(dec(x))
    if x == 0:
        return Decimal("0")
    n_sig = sig_digits_for_uncertainty(x)
    return round_sig_half_even(x, n_sig)


def needs_scientific_notation_for_sig(x: Decimal, sig_digits: int) -> bool:
    """
    Evita ambiguidades do tipo 100, 120, 1000 etc., quando o número de AS
    ficaria escondido na escrita decimal usual.
    """
    x = abs(dec(x))
    if x == 0:
        return False
    exponent = x.adjusted()

    # Para inteiros grandes em que a escrita comum esconde os AS:
    # ex.: 100 com 1 AS; 120 com 2 AS; 1000 com 1 AS etc.
    if exponent >= sig_digits:
        return True

    # Para números muito pequenos, a escrita científica também pode ajudar;
    # aqui mantive apenas casos realmente pequenos.
    if x != 0 and exponent <= -4:
        return True

    return False


def format_sig_display_br(x: Decimal, sig_digits: int) -> str:
    """
    Formata número arredondado para N AS.
    Se a escrita decimal ficar ambígua, usa notação científica:
    ex.: 1 × 10²
    """
    rounded = round_sig_half_even(dec(x), sig_digits)

    if rounded == 0:
        return "0"

    if needs_scientific_notation_for_sig(rounded, sig_digits):
        exponent = rounded.adjusted()
        mantissa = rounded.scaleb(-exponent)

        # quantiza mantissa para manter exatamente os sig_digits
        mantissa_quant = Decimal(f"1e-{sig_digits-1}") if sig_digits > 1 else Decimal("1")
        mantissa = mantissa.quantize(mantissa_quant, rounding=ROUND_HALF_EVEN)

        mantissa_places = count_decimal_places_preserved(mantissa)
        mantissa_str = decimal_to_br_fixed(mantissa, mantissa_places)

        if exponent == 0:
            return mantissa_str
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


def round_value_to_match_uncertainty(value: Decimal, uncertainty: Decimal) -> Decimal:
    """
    Arredonda 'value' para o mesmo número de casas decimais de 'uncertainty'
    (na representação decimal do Decimal).
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
    Gera 5 medições próximas do valor central, usando resolução de 0,05 mm.
    """
    center = dec(center)
    rng = random.Random(seed)
    step = Decimal("0.05")

    offsets = [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]
    values = []

    for _ in range(5):
        k = rng.choice(offsets)
        v = center + Decimal(k) * step
        if v <= 0:
            v = Decimal("0.05")
        v = quant_step(v, step)
        values.append(v.quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN))

    # evita todos iguais
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


def cylinder_svg(d_mm: float, l_mm: float) -> tuple[str, int]:
    """
    Cilindro vertical em SVG, com:
    - diâmetro D no topo
    - altura L à direita
    - base inferior com arco traseiro tracejado
    - layout largo com rolagem horizontal no celular
    """
    # Escalas visuais
    body_w = max(210.0, 140.0 + 4.2 * d_mm)
    body_h = max(260.0, 120.0 + 4.8 * l_mm)

    ellipse_rx = body_w / 2.0
    ellipse_ry = max(30.0, ellipse_rx * 0.22)

    margin_left = 90.0
    margin_top = 55.0
    margin_right = 120.0
    margin_bottom = 55.0

    x_center = margin_left + ellipse_rx
    top_y = margin_top + ellipse_ry
    bottom_y = top_y + body_h

    left_x = x_center - ellipse_rx
    right_x = x_center + ellipse_rx

    total_w = int(margin_left + body_w + margin_right)
    total_h = int(margin_top + body_h + 2 * ellipse_ry + margin_bottom + 20)

    d_text = f"D = {d_mm:.2f} mm".replace(".", ",")
    l_text = f"L = {l_mm:.2f} mm".replace(".", ",")

    # Linha do diâmetro no topo
    d_y = top_y - ellipse_ry * 0.15
    d_text_x = x_center
    d_text_y = d_y + 46

    # Cota vertical de L
    dim_x = right_x + 48
    dim_y1 = top_y - ellipse_ry * 0.15
    dim_y2 = bottom_y + ellipse_ry * 0.15

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
          style="display:block; max-width:none; user-select:none;"
          preserveAspectRatio="xMinYMin meet"
      >
        <defs>
          <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stop-color="#6f70d9"/>
            <stop offset="50%" stop-color="#7677df"/>
            <stop offset="100%" stop-color="#6a6ccc"/>
          </linearGradient>
          <marker id="arrowThin" viewBox="0 0 10 10" refX="5" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#111111"/>
          </marker>
        </defs>

        <!-- corpo -->
        <rect x="{left_x}" y="{top_y}" width="{body_w}" height="{body_h}"
              fill="url(#bodyGrad)" opacity="0.95"/>

        <!-- laterais -->
        <line x1="{left_x}" y1="{top_y}" x2="{left_x}" y2="{bottom_y}"
              stroke="#1022ff" stroke-width="3"/>
        <line x1="{right_x}" y1="{top_y}" x2="{right_x}" y2="{bottom_y}"
              stroke="#1022ff" stroke-width="3"/>

        <!-- topo -->
        <ellipse cx="{x_center}" cy="{top_y}" rx="{ellipse_rx}" ry="{ellipse_ry}"
                 fill="#8b8ce9" stroke="#1022ff" stroke-width="3"/>

        <!-- base inferior: arco traseiro tracejado -->
        <path d="M {left_x},{bottom_y}
                 A {ellipse_rx},{ellipse_ry} 0 0 1 {right_x},{bottom_y}"
              fill="none" stroke="#1022ff" stroke-width="3"
              stroke-dasharray="12 10" opacity="0.9"/>

        <!-- base inferior: arco frontal contínuo -->
        <path d="M {right_x},{bottom_y}
                 A {ellipse_rx},{ellipse_ry} 0 0 1 {left_x},{bottom_y}"
              fill="none" stroke="#1022ff" stroke-width="3"/>

        <!-- diâmetro do topo -->
        <line x1="{left_x}" y1="{d_y}" x2="{right_x}" y2="{d_y}"
              stroke="#111111" stroke-width="3"/>
        <circle cx="{left_x}" cy="{d_y}" r="6" fill="#111111"/>
        <circle cx="{x_center}" cy="{d_y}" r="6" fill="#111111"/>
        <circle cx="{right_x}" cy="{d_y}" r="6" fill="#111111"/>

        <text x="{d_text_x}" y="{d_text_y}" text-anchor="middle"
              font-size="52" font-family="Times New Roman, serif"
              font-style="italic" fill="#111111">D</text>

        <text x="{x_center}" y="{top_y - ellipse_ry - 12}" text-anchor="middle"
              font-size="24" font-family="Arial, sans-serif" fill="#111111">{d_text}</text>

        <!-- cota da altura -->
        <line x1="{dim_x}" y1="{dim_y1}" x2="{dim_x}" y2="{dim_y2}"
              stroke="#111111" stroke-width="2.8"
              marker-start="url(#arrowThin)" marker-end="url(#arrowThin)"/>
        <line x1="{right_x + 14}" y1="{dim_y1}" x2="{dim_x - 10}" y2="{dim_y1}"
              stroke="#111111" stroke-width="2"/>
        <line x1="{right_x + 14}" y1="{dim_y2}" x2="{dim_x - 10}" y2="{dim_y2}"
              stroke="#111111" stroke-width="2"/>

        <text x="{dim_x + 34}" y="{(dim_y1 + dim_y2)/2 + 10}" text-anchor="start"
              font-size="58" font-family="Times New Roman, serif"
              font-style="italic" fill="#111111">L</text>

        <text x="{dim_x + 34}" y="{(dim_y1 + dim_y2)/2 + 44}" text-anchor="start"
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
    logo_path = Path("logo_maua.png")
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
    else:
        st.warning("Arquivo logo_maua.png não encontrado.")

with col_title:
    st.title("Prática Propagação de Incerteza")
    st.write(
        "Pratique como informar o resultado final do volume "
        r"$V$ de um cilindro, incluindo sua incerteza, considerando medições "
        r"com paquímetro de resolução $\sigma_{instr} = \pm 0{,}05\ \mathrm{mm}$."
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
        min_value=0.01,
        max_value=100.00,
        value=20.00,
        step=0.01,
        format="%.2f",
    )

with col_p2:
    L_slider = st.slider(
        "Comprimento aproximado do cilindro L (mm)",
        min_value=0.01,
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
st.caption("Em celular, arraste horizontalmente para observar toda a figura. O zoom da imagem permanece fixo.")
svg_html, svg_height = cylinder_svg(float(D_slider), float(L_slider))
components.html(svg_html, height=svg_height, scrolling=False)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# GERAÇÃO DOS VALORES ALEATÓRIOS
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

sigma_est_D_round = round_uncertainty(sigma_est_D)
sigma_est_L_round = round_uncertainty(sigma_est_L)

sigma_comb_D_raw = calc_combined(sigma_est_D_round, SIGMA_INSTR)
sigma_comb_L_raw = calc_combined(sigma_est_L_round, SIGMA_INSTR)

sigma_comb_D = round_uncertainty(sigma_comb_D_raw)
sigma_comb_L = round_uncertainty(sigma_comb_L_raw)

D_result = round_value_to_match_uncertainty(Dm, sigma_comb_D)
L_result = round_value_to_match_uncertainty(Lm, sigma_comb_L)

PI_DEC = Decimal(str(math.pi))
V_raw = (PI_DEC * (Dm ** 2) / Decimal("4")) * Lm

sigma_V_raw = abs(V_raw) * sqrt_decimal(
    (Decimal("2") * sigma_comb_D / Dm) ** 2 +
    (sigma_comb_L / Lm) ** 2
)

sigma_V = round_uncertainty(sigma_V_raw)
V_result = round_value_to_match_uncertainty(V_raw, sigma_V)

# ============================================================
# VISIBILIDADE INICIAL APENAS DOS DADOS GERADOS
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
    '<p class="small-note">Abra as seções abaixo para visualizar o passo a passo dos cálculos.</p>',
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# D. INCERTEZA INSTRUMENTAL
# ============================================================
with st.expander("D. Incerteza instrumental", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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

        st.write(
            f"Resultado sem arredondamento: σ_est = {decimal_to_br_plain(sigma_est_D, 12)} mm"
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

        st.write(
            f"Resultado arredondado: σ_est = "
            f"{format_sig_display_br(sigma_est_D, sig_digits_for_uncertainty(sigma_est_D))} mm"
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

        st.write(
            f"Resultado sem arredondamento: σ_est = {decimal_to_br_plain(sigma_est_L, 12)} mm"
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

        st.write(
            f"Resultado arredondado: σ_est = "
            f"{format_sig_display_br(sigma_est_L, sig_digits_for_uncertainty(sigma_est_L))} mm"
        )

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# F. INCERTEZA COMBINADA
# ============================================================
with st.expander("F. Incerteza combinada", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Incerteza combinada")

    tab_Dc, tab_Lc = st.tabs(["Diâmetro D", "Comprimento L"])

    with tab_Dc:
        st.write("Equação da incerteza combinada:")
        st.latex(r"\sigma_{comb} = \sqrt{\sigma_{est}^{2} + \sigma_{instr}^{2}}")

        st.write("Substituindo os valores arredondados:")
        st.latex(
            rf"\sigma_{{comb}} = \sqrt{{\left({format_sig_display_latex(sigma_est_D, sig_digits_for_uncertainty(sigma_est_D))}\right)^2 + \left(0{{,}}05\right)^2}}"
        )

        st.write(
            f"Resultado sem arredondamento: σ_comb = {decimal_to_br_plain(sigma_comb_D_raw, 12)} mm"
        )

        st.write(
            f"Resultado final arredondado: σ_comb = "
            f"{format_sig_display_br(sigma_comb_D_raw, sig_digits_for_uncertainty(sigma_comb_D_raw))} mm"
        )

        st.info(
            "Como a incerteza instrumental tem apenas um algarismo significativo, "
            "a incerteza combinada fica limitada a ter apenas um algarismo significativo."
        )

    with tab_Lc:
        st.write("Equação da incerteza combinada:")
        st.latex(r"\sigma_{comb} = \sqrt{\sigma_{est}^{2} + \sigma_{instr}^{2}}")

        st.write("Substituindo os valores arredondados:")
        st.latex(
            rf"\sigma_{{comb}} = \sqrt{{\left({format_sig_display_latex(sigma_est_L, sig_digits_for_uncertainty(sigma_est_L))}\right)^2 + \left(0{{,}}05\right)^2}}"
        )

        st.write(
            f"Resultado sem arredondamento: σ_comb = {decimal_to_br_plain(sigma_comb_L_raw, 12)} mm"
        )

        st.write(
            f"Resultado final arredondado: σ_comb = "
            f"{format_sig_display_br(sigma_comb_L_raw, sig_digits_for_uncertainty(sigma_comb_L_raw))} mm"
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
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Resultado das medições")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        sigma_D_places = count_decimal_places_preserved(sigma_comb_D)
        sigma_D_display = (
            format_sig_display_br(sigma_comb_D, sig_digits_for_uncertainty(sigma_comb_D))
            if needs_scientific_notation_for_sig(sigma_comb_D, sig_digits_for_uncertainty(sigma_comb_D))
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
        st.caption("O valor médio é arredondado para apresentar o mesmo número de casas decimais da incerteza combinada.")

    with col_g2:
        sigma_L_places = count_decimal_places_preserved(sigma_comb_L)
        sigma_L_display = (
            format_sig_display_br(sigma_comb_L, sig_digits_for_uncertainty(sigma_comb_L))
            if needs_scientific_notation_for_sig(sigma_comb_L, sig_digits_for_uncertainty(sigma_comb_L))
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
        st.caption("O valor médio é arredondado para apresentar o mesmo número de casas decimais da incerteza combinada.")

    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# H. VOLUME
# ============================================================
with st.expander("H. Volume", expanded=False):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
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
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Incerteza do volume")

    st.write(
        "Como o volume foi calculado a partir de medições com incertezas, "
        "é necessário aplicar o conceito de propagação de incerteza. "
        "No caso de produto entre duas medições:"
    )

    st.latex(
        r"\sigma_{V} = V\sqrt{\left(\frac{2\sigma_{D}}{D}\right)^2 + \left(\frac{\sigma_{L}}{L}\right)^2}"
    )

    sigma_D_for_eq = (
        format_sig_display_latex(sigma_comb_D, sig_digits_for_uncertainty(sigma_comb_D))
        if needs_scientific_notation_for_sig(sigma_comb_D, sig_digits_for_uncertainty(sigma_comb_D))
        else latex_decimal_fixed(sigma_comb_D, count_decimal_places_preserved(sigma_comb_D))
    )
    sigma_L_for_eq = (
        format_sig_display_latex(sigma_comb_L, sig_digits_for_uncertainty(sigma_comb_L))
        if needs_scientific_notation_for_sig(sigma_comb_L, sig_digits_for_uncertainty(sigma_comb_L))
        else latex_decimal_fixed(sigma_comb_L, count_decimal_places_preserved(sigma_comb_L))
    )

    st.write("Substituindo os valores:")
    st.latex(
        rf"\sigma_{{V}} = {latex_decimal_plain(V_raw, 12)}\sqrt{{\left(\frac{{2\cdot {sigma_D_for_eq}}}{{{latex_decimal_plain(Dm, 12)}}}\right)^2 + \left(\frac{{{sigma_L_for_eq}}}{{{latex_decimal_plain(Lm, 12)}}}\right)^2}}"
    )

    st.write(f"Resultado sem arredondamento: σ_V = {decimal_to_br_plain(sigma_V_raw, 12)} mm³")
    st.write(
        f"Resultado arredondado: σ_V = "
        f"{format_sig_display_br(sigma_V_raw, sig_digits_for_uncertainty(sigma_V_raw))} mm³"
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
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("Resultado final")

    sigma_V_places = count_decimal_places_preserved(sigma_V)

    sigma_V_display = (
        format_sig_display_br(sigma_V, sig_digits_for_uncertainty(sigma_V))
        if needs_scientific_notation_for_sig(sigma_V, sig_digits_for_uncertainty(sigma_V))
        else decimal_to_br_fixed(sigma_V, sigma_V_places)
    )

    V_display = format_value_matching_uncertainty_br(V_raw, sigma_V)

    st.markdown(
        f"""
        <div class="result-box" style="font-size: 1.15rem;">
        <b>V = {V_display} ± {sigma_V_display} mm³</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("O valor do volume é arredondado para apresentar o mesmo número de casas decimais da incerteza.")

    st.markdown('</div>', unsafe_allow_html=True)
