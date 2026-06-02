import math
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================
st.set_page_config(
    page_title="Prática Propagação de Incerteza",
    layout="wide",
    initial_sidebar_state="collapsed",
)

getcontext().prec = 40  # boa precisão para contas com Decimal

SIGMA_INSTR = Decimal("0.05")  # mm

# =========================================================
# ESTILO
# =========================================================
st.markdown(
    """
    <style>
        .main {
            padding-top: 1rem;
        }
        .section-card {
            padding: 1rem 1.2rem;
            border: 1px solid rgba(120,120,120,0.25);
            border-radius: 14px;
            background-color: rgba(250,250,250,0.55);
            margin-bottom: 1rem;
        }
        .small-note {
            font-size: 0.95rem;
            color: #444;
        }
        .result-box {
            padding: 0.9rem 1rem;
            border-radius: 12px;
            border: 1px solid rgba(0,0,0,0.15);
            background: #f7f9fc;
            margin-top: 0.5rem;
            margin-bottom: 0.7rem;
        }
        .centered {
            text-align: center;
        }
        .foot {
            font-size: 0.92rem;
            color: #333;
        }
        .mono {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }
        /* melhora a leitura em celular */
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

# =========================================================
# FUNÇÕES AUXILIARES (ARREDONDAMENTO E FORMATAÇÃO)
# =========================================================

def dec(x) -> Decimal:
    """Converte para Decimal preservando representação textual."""
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def decimal_to_plain_str(d: Decimal) -> str:
    """Converte Decimal para string sem notação científica."""
    d = dec(d)
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".") if s.rstrip("0").rstrip(".") != "-0" else "0"
    return s


def format_fixed(d: Decimal, places: int) -> str:
    """Formata Decimal com número fixo de casas decimais."""
    d = dec(d)
    q = Decimal(1).scaleb(-places)
    d = d.quantize(q, rounding=ROUND_HALF_EVEN)
    return f"{d:.{places}f}"


def count_decimal_places(d: Decimal) -> int:
    """Conta casas decimais de um Decimal já quantizado/formatado."""
    d = dec(d)
    exponent = d.as_tuple().exponent
    return -exponent if exponent < 0 else 0


def first_significant_digit(x: Decimal) -> int:
    """Retorna o primeiro algarismo significativo."""
    x = abs(dec(x))
    if x == 0:
        return 0
    normalized = x.normalize()
    return normalized.as_tuple().digits[0]


def significant_digits_rule_uncertainty(x: Decimal) -> int:
    """
    Regra:
    - 1 algarismo significativo
    - exceto se o primeiro AS for 1 ou 2, então usar 2 AS
    """
    fd = first_significant_digit(x)
    return 2 if fd in (1, 2) else 1


def round_sig_half_even(x: Decimal, sig_digits: int) -> Decimal:
    """
    Arredondamento para N algarismos significativos usando ROUND_HALF_EVEN,
    que implementa:
      - >5 sobe
      - <5 mantém
      - 5 exato (ou 5 seguido apenas de zeros) vai para o par
    """
    x = dec(x)
    if x == 0:
        return Decimal("0")
    exponent = x.adjusted()  # expoente do primeiro dígito significativo
    quant = Decimal(f"1e{exponent - sig_digits + 1}")
    return x.quantize(quant, rounding=ROUND_HALF_EVEN)


def round_uncertainty(x: Decimal) -> Decimal:
    """Arredonda incerteza pela regra de 1 AS, exceto 1 ou 2 no primeiro AS => 2 AS."""
    x = abs(dec(x))
    if x == 0:
        return Decimal("0")
    sig = significant_digits_rule_uncertainty(x)
    return round_sig_half_even(x, sig)


def round_value_to_uncertainty_decimal_places(value: Decimal, uncertainty: Decimal) -> Decimal:
    """
    Arredonda o valor para o mesmo número de casas decimais da incerteza.
    """
    value = dec(value)
    uncertainty = dec(uncertainty)
    places = count_decimal_places(uncertainty.normalize()) if uncertainty != 0 else 0
    q = Decimal(1).scaleb(-places)
    return value.quantize(q, rounding=ROUND_HALF_EVEN)


def sqrt_decimal(x: Decimal) -> Decimal:
    x = dec(x)
    if x < 0:
        raise ValueError("Não é possível tirar raiz quadrada de valor negativo.")
    return x.sqrt()


def decimal_from_float_1_decimal(x: float) -> Decimal:
    """
    Converte slider (uma casa decimal) em Decimal correto.
    """
    return Decimal(f"{x:.1f}")


def sum_of_squares(vals):
    total = Decimal("0")
    for v in vals:
        total += dec(v) * dec(v)
    return total


def generate_measurements_around(center: Decimal, rng: np.random.Generator):
    """
    Gera 5 medições próximas do valor central, quantizadas em 0,05 mm.
    Mantém valores positivos e busca evitar todos iguais.
    """
    center = dec(center)
    step = Decimal("0.05")

    # Amplitude moderada para gerar diversidade sem se afastar demais
    # passos inteiros de 0,05 mm
    raw_steps = rng.integers(-4, 5, size=5)

    # evita todos iguais
    if len(set(raw_steps.tolist())) == 1:
        raw_steps[0] = raw_steps[0] + 1 if raw_steps[0] < 4 else raw_steps[0] - 1

    values = []
    for s in raw_steps:
        v = center + Decimal(int(s)) * step
        if v <= Decimal("0"):
            v = Decimal("0.05")
        values.append(v.quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN))

    # Se por acaso ficarem todos iguais, força pequena diferença
    if len(set(values)) == 1:
        values[0] = (values[0] + step).quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN)

    return values


def calculate_statistical_uncertainty(values):
    """
    Para lista de 5 Decimals:
      Dm = média
      desvios = (Di - Dm)
      quadrados = (Di - Dm)^2
      sigma_est = sqrt(sum(quadrados) / (n(n-1)))
    """
    n = Decimal(len(values))
    mean = sum(values, Decimal("0")) / n
    deviations = [v - mean for v in values]
    squares = [d * d for d in deviations]
    sigma_est = sqrt_decimal(sum(squares, Decimal("0")) / (n * (n - 1)))
    return mean, deviations, squares, sigma_est


def calculate_combined_uncertainty(sigma_est_rounded: Decimal, sigma_instr: Decimal = SIGMA_INSTR):
    """
    sigma_comb = sqrt(sigma_est^2 + sigma_instr^2)
    Mostrará substituição com sigma_est arredondado e sigma_instr.
    """
    sigma_est_rounded = abs(dec(sigma_est_rounded))
    sigma_instr = abs(dec(sigma_instr))
    sigma_comb = sqrt_decimal(sigma_est_rounded**2 + sigma_instr**2)
    return sigma_comb


def safe_display_decimal(d: Decimal, max_places: int = 12) -> str:
    """
    Mostra Decimal com até max_places casas, sem notação científica.
    Se houver mais casas, mantém até max_places.
    """
    d = dec(d)
    q = Decimal(1).scaleb(-max_places)
    displayed = d.quantize(q, rounding=ROUND_HALF_EVEN)
    s = f"{displayed:.{max_places}f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s


def build_stats_table(measurements, mean, deviations=None, squares=None, symbol_name="D"):
    """
    Monta tabelas:
    - básica: Medição + valor + última linha com n=5 / média
    - completa: Medição + valor + (xi - média) + quadrado + última linha
    """
    basic_rows = []
    for i, v in enumerate(measurements, start=1):
        basic_rows.append(
            {
                "Medição": str(i),
                f"{symbol_name}i (mm)": format_fixed(v, 2),
            }
        )
    basic_rows.append(
        {
            "Medição": "n = 5",
            f"{symbol_name}i (mm)": f"{symbol_name}m = {safe_display_decimal(mean, 12)}",
        }
    )
    df_basic = pd.DataFrame(basic_rows)

    if deviations is None or squares is None:
        return df_basic, None

    full_rows = []
    for i, (v, dv, sq) in enumerate(zip(measurements, deviations, squares), start=1):
        full_rows.append(
            {
                "Medição": str(i),
                f"{symbol_name}i (mm)": format_fixed(v, 2),
                f"({symbol_name}i - {symbol_name}m) (mm)": safe_display_decimal(dv, 12),
                f"({symbol_name}i - {symbol_name}m)² (mm²)": safe_display_decimal(sq, 12),
            }
        )
    full_rows.append(
        {
            "Medição": "n = 5",
            f"{symbol_name}i (mm)": f"{symbol_name}m = {safe_display_decimal(mean, 12)}",
            f"({symbol_name}i - {symbol_name}m) (mm)": "—",
            f"({symbol_name}i - {symbol_name}m)² (mm²)": "—",
        }
    )
    df_full = pd.DataFrame(full_rows)
    return df_basic, df_full


def make_cylinder_svg(d_mm: float, l_mm: float):
    """
    Gera SVG pseudo-3D de um cilindro horizontal.
    - dimensão L cresce em largura
    - dimensão D cresce em altura
    - container com overflow horizontal para celular
    - sem zoom; apenas rolagem/pan do container
    """
    # Escalas visuais
    body_length_px = 420 + 6.0 * float(l_mm)  # cresce com L
    diameter_px = max(80, 70 + 3.6 * float(d_mm))  # cresce com D

    margin_left = 130
    margin_right = 120
    margin_top = 60
    margin_bottom = 120

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

    # Cotas
    # Diâmetro à esquerda
    dim_x = x0 - 55
    dim_y1 = rect_y
    dim_y2 = rect_y + rect_h

    # Comprimento abaixo
    len_y = rect_y + rect_h + 55
    len_x1 = rect_x
    len_x2 = rect_x + rect_w

    d_label = f"D = {d_mm:.1f} mm"
    l_label = f"L = {l_mm:.1f} mm"

    svg = f"""
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
            <stop offset="0%" style="stop-color:#d9e6f2;stop-opacity:1" />
            <stop offset="50%" style="stop-color:#a9c7df;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#7ea5c7;stop-opacity:1" />
          </linearGradient>
          <linearGradient id="faceGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#eef5fb;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#93b7d4;stop-opacity:1" />
          </linearGradient>
          <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#111"/>
          </marker>
          <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.20"/>
          </filter>
        </defs>

        <!-- corpo -->
        <g filter="url(#shadow)">
          <rect x="{rect_x}" y="{rect_y}" width="{rect_w}" height="{rect_h}"
                fill="url(#bodyGrad)" stroke="#4d6f89" stroke-width="2"/>
          <!-- face traseira -->
          <ellipse cx="{rect_x + rect_w}" cy="{y0}" rx="{rx}" ry="{ry}"
                   fill="#7ea5c7" stroke="#4d6f89" stroke-width="2"/>
          <!-- face frontal -->
          <ellipse cx="{x0 + rx}" cy="{y0}" rx="{rx}" ry="{ry}"
                   fill="url(#faceGrad)" stroke="#4d6f89" stroke-width="2"/>
        </g>

        <!-- destaques -->
        <ellipse cx="{x0 + rx}" cy="{y0 - ry*0.15}" rx="{rx*0.82}" ry="{ry*0.55}"
                 fill="rgba(255,255,255,0.35)" />
        <ellipse cx="{rect_x + rect_w}" cy="{y0 - ry*0.10}" rx="{rx*0.78}" ry="{ry*0.45}"
                 fill="rgba(255,255,255,0.18)" />

        <!-- cotas do diâmetro -->
        <line x1="{dim_x}" y1="{dim_y1}" x2="{dim_x}" y2="{dim_y2}"
              stroke="#111" stroke-width="2"
              marker-start="url(#arrow)" marker-end="url(#arrow)" />
        <line x1="{dim_x+12}" y1="{dim_y1}" x2="{x0+5}" y2="{dim_y1}"
              stroke="#111" stroke-width="1.6"/>
        <line x1="{dim_x+12}" y1="{dim_y2}" x2="{x0+5}" y2="{dim_y2}"
              stroke="#111" stroke-width="1.6"/>
        <text x="{dim_x-
