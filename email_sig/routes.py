import os
from flask import Blueprint, render_template, request, jsonify, Response
from config import get_groq_key
from translations import get_t

bp = Blueprint('email_sig', __name__, template_folder='templates')

# ── Font-size presets ──────────────────────────────────────────────────────
FONT_SIZES = {
    'small':  {'name': 14, 'title': 11, 'contact': 11, 'tagline': 10},
    'medium': {'name': 17, 'title': 13, 'contact': 12, 'tagline': 11},
    'large':  {'name': 22, 'title': 15, 'contact': 13, 'tagline': 12},
}


def get_groq_client():
    from groq import Groq
    key = get_groq_key()
    if not key:
        raise ValueError('GROQ_API_KEY not set. Configure it in Admin → API Keys.')
    return Groq(api_key=key)


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    if len(h) != 6:
        return (100, 100, 100)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _darken(hex_color, factor=0.72):
    try:
        r, g, b = _hex_to_rgb(hex_color)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"
    except Exception:
        return hex_color


def _rgba(hex_color, alpha=0.08):
    try:
        r, g, b = _hex_to_rgb(hex_color)
        return f"rgba({r},{g},{b},{alpha})"
    except Exception:
        return '#f5f5f5'


def build_signature_html(name, title, company, email, phone, website, linkedin,
                          twitter, tagline, accent_color, font, template,
                          font_size='medium'):
    accent = accent_color or '#a855f7'
    accent_light = _rgba(accent, 0.07)

    sz = FONT_SIZES.get(font_size, FONT_SIZES['medium'])
    ns = sz['name']      # name size
    ts = sz['title']     # title/role size
    cs = sz['contact']   # contact size
    gs = sz['tagline']   # tagline size

    font_stack = f"{font}, Arial, sans-serif" if font else "Arial, sans-serif"

    # Avatar initial
    initial = name[0].upper() if name else '?'

    # ── Link helpers ──────────────────────────────────────────────────────
    def mailto(addr):
        return (f'<a href="mailto:{addr}" style="color:#555;text-decoration:none">{addr}</a>'
                if addr else '')

    def weblink(url):
        if not url:
            return ''
        label = url.replace('https://', '').replace('http://', '').rstrip('/')
        return f'<a href="{url}" style="color:#555;text-decoration:none">{label}</a>'

    email_link   = mailto(email)
    website_link = weblink(website)

    li_handle = linkedin.rstrip('/').split('/')[-1] if linkedin else ''
    tw_handle = twitter.lstrip('@') if twitter else ''
    li_link = (f'<a href="{linkedin}" style="color:{accent};text-decoration:none;font-weight:600">'
               f'in/{li_handle}</a>') if linkedin else ''
    tw_link = (f'<a href="https://twitter.com/{tw_handle}" style="color:{accent};'
               f'text-decoration:none;font-weight:600">@{tw_handle}</a>') if twitter else ''

    dot = '<span style="color:#ddd">&nbsp;·&nbsp;</span>'

    contact_parts = [x for x in [email_link,
                                  f'<span style="color:#555">{phone}</span>' if phone else '',
                                  website_link] if x]
    contact_row = dot.join(contact_parts)

    social_parts = [x for x in [li_link, tw_link] if x]
    social_row = dot.join(social_parts)

    title_company = ''
    if title and company:
        title_company = f'{title} &nbsp;·&nbsp; {company}'
    elif title:
        title_company = title
    elif company:
        title_company = company

    tpl = (template or 'modern').lower()

    # ════════════════════════════════════════════════════════════════════════
    # 1. MODERN — left accent border, clean hierarchy, subtle rule
    # ════════════════════════════════════════════════════════════════════════
    if tpl == 'modern':
        tag_html = (f'<div style="font-size:{gs}px;color:#999;font-style:italic;'
                    f'margin-top:4px;line-height:1.5">{tagline}</div>') if tagline else ''
        soc_html = (f'<div style="margin-top:4px;font-size:{cs}px">{social_row}</div>') if social_row else ''
        tc_html  = (f'<div style="font-size:{ts}px;color:{accent};font-weight:600;margin-top:3px">'
                    f'{title_company}</div>') if title_company else ''
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:500px;margin:0">
  <tr>
    <td style="border-left:4px solid {accent};padding:6px 16px 8px 14px">
      <div style="font-size:{ns}px;font-weight:700;color:#111;letter-spacing:-0.3px;line-height:1.2">{name}</div>
      {tc_html}
      {tag_html}
    </td>
  </tr>
  <tr>
    <td style="padding:7px 0 0 18px">
      <div style="border-top:1px solid #ebebeb;padding-top:7px;font-size:{cs}px;color:#666;line-height:1.9">
        {contact_row}
        {soc_html}
      </div>
    </td>
  </tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 2. CLASSIC — full-width accent header, two-column body
    # ════════════════════════════════════════════════════════════════════════
    elif tpl == 'classic':
        tc_html = (f'<div style="font-size:{ts}px;color:rgba(255,255,255,0.85);'
                   f'margin-top:3px;font-weight:500">{title_company}</div>') if title_company else ''
        left_col = ''.join([
            f'<div style="margin-bottom:3px">{email_link}</div>' if email_link else '',
            f'<div style="margin-bottom:3px;color:#555">{phone}</div>' if phone else '',
            f'<div>{website_link}</div>' if website_link else '',
        ])
        right_col = ''.join([
            f'<div style="color:#888;font-style:italic;margin-bottom:8px;line-height:1.5">{tagline}</div>' if tagline else '',
            f'<div>{social_row}</div>' if social_row else '',
        ])
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:500px;margin:0">
  <tr>
    <td colspan="2" style="background:{accent};padding:12px 16px 11px">
      <div style="font-size:{ns}px;font-weight:800;color:#fff;letter-spacing:-0.3px;line-height:1.2">{name}</div>
      {tc_html}
    </td>
  </tr>
  <tr>
    <td style="padding:11px 14px 11px 16px;border:1px solid #e8e8e8;border-top:none;border-right:none;font-size:{cs}px;color:#444;vertical-align:top;min-width:180px;line-height:1.9">
      {left_col}
    </td>
    <td style="padding:11px 16px 11px 14px;border:1px solid #e8e8e8;border-top:none;border-left:none;font-size:{cs}px;color:#444;vertical-align:top;line-height:1.9">
      {right_col}
    </td>
  </tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 3. MINIMAL — everything inline, ultra-clean
    # ════════════════════════════════════════════════════════════════════════
    elif tpl == 'minimal':
        sep = '<span style="color:#ddd;font-size:13px;margin:0 6px">|</span>'
        name_parts = []
        if name:    name_parts.append(f'<strong style="color:#111;font-size:{ns}px">{name}</strong>')
        if title:   name_parts.append(f'<span style="color:#888;font-size:{ts}px">{title}</span>')
        if company: name_parts.append(f'<span style="color:{accent};font-size:{ts}px;font-weight:600">{company}</span>')
        header = sep.join(name_parts)

        all_c = [x for x in [email_link,
                               f'<span style="color:#555">{phone}</span>' if phone else '',
                               website_link, li_link, tw_link] if x]
        contact_full = dot.join(all_c)
        tag_row = (f'<tr><td style="font-size:{gs}px;color:#bbb;font-style:italic;'
                   f'padding-bottom:5px;line-height:1.4">{tagline}</td></tr>') if tagline else ''
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:560px;margin:0">
  <tr><td style="padding-bottom:5px">{header}</td></tr>
  {tag_row}
  <tr>
    <td style="font-size:{cs}px;color:#777;border-top:1px solid #ececec;padding-top:7px;line-height:1.9">
      {contact_full}
    </td>
  </tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 4. BOLD — oversized name, thick accent underline bar, caps title
    # ════════════════════════════════════════════════════════════════════════
    elif tpl == 'bold':
        tc_caps = title_company.upper() if title_company else ''
        tc_html = (f'<div style="font-size:{ts - 1}px;color:{accent};font-weight:800;'
                   f'letter-spacing:1.4px;margin-top:6px">{tc_caps}</div>') if tc_caps else ''
        tag_html = (f'<div style="font-size:{gs}px;color:#888;font-style:italic;'
                    f'margin-top:8px;line-height:1.5">{tagline}</div>') if tagline else ''
        soc_html = (f'<div style="margin-top:5px;font-size:{cs}px">{social_row}</div>') if social_row else ''
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:500px;margin:0">
  <tr>
    <td style="padding-bottom:10px">
      <div style="font-size:{ns + 6}px;font-weight:900;color:#111;letter-spacing:-0.6px;line-height:1.05">{name}</div>
      <div style="height:4px;background:{accent};width:52px;margin:8px 0 2px;border-radius:3px"></div>
      {tc_html}
      {tag_html}
    </td>
  </tr>
  <tr>
    <td style="padding-top:10px;border-top:1px solid #f0f0f0;font-size:{cs}px;color:#555;line-height:1.9">
      {contact_row}
      {soc_html}
    </td>
  </tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 5. EXECUTIVE — accent avatar circle, vertical divider, rich contact
    # ════════════════════════════════════════════════════════════════════════
    elif tpl == 'executive':
        avatar_size = ns + 18
        tc_html = (f'<div style="font-size:{ts}px;color:{accent};font-weight:600;margin-top:3px">'
                   f'{title_company}</div>') if title_company else ''
        tag_html = (f'<div style="font-size:{gs}px;color:#aaa;font-style:italic;margin-top:3px;'
                    f'line-height:1.4">{tagline}</div>') if tagline else ''
        soc_html = (f'<div style="margin-top:5px;font-size:{cs}px">{social_row}</div>') if social_row else ''
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:520px;margin:0">
  <tr>
    <td style="vertical-align:middle;padding-right:16px;padding-bottom:10px">
      <div style="width:{avatar_size}px;height:{avatar_size}px;background:{accent};border-radius:50%;
                  text-align:center;line-height:{avatar_size}px;font-size:{ns + 2}px;
                  font-weight:900;color:#fff">{initial}</div>
    </td>
    <td style="vertical-align:top;border-left:2px solid {accent};padding-left:14px;padding-bottom:10px">
      <div style="font-size:{ns}px;font-weight:700;color:#111;letter-spacing:-0.2px;line-height:1.2">{name}</div>
      {tc_html}
      {tag_html}
    </td>
  </tr>
  <tr>
    <td colspan="2" style="border-top:1px solid #ebebeb;padding-top:8px;font-size:{cs}px;color:#666;line-height:1.9">
      {contact_row}
      {soc_html}
    </td>
  </tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 6. CREATIVE — accent left panel with initial, right panel details
    # ════════════════════════════════════════════════════════════════════════
    elif tpl == 'creative':
        right_title  = f'<div style="font-size:{ts}px;font-weight:700;color:#333;margin-bottom:2px">{title}</div>' if title else ''
        right_co     = f'<div style="font-size:{ts - 1}px;color:{accent};font-weight:600;margin-bottom:9px">{company}</div>' if company else ''
        right_tag    = (f'<div style="font-size:{gs}px;color:#bbb;font-style:italic;margin-bottom:10px;'
                        f'line-height:1.5">{tagline}</div>') if tagline else ''
        contact_block = ''.join([
            f'<div style="margin-bottom:3px">{email_link}</div>' if email_link else '',
            f'<div style="margin-bottom:3px;color:#555">{phone}</div>' if phone else '',
            f'<div style="margin-bottom:3px">{website_link}</div>' if website_link else '',
            f'<div style="margin-top:5px">{social_row}</div>' if social_row else '',
        ])
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:520px;margin:0">
  <tr>
    <td style="background:{accent};padding:20px 14px;vertical-align:middle;text-align:center;width:90px">
      <div style="font-size:{ns + 10}px;font-weight:900;color:#fff;line-height:1">{initial}</div>
      <div style="height:2px;background:rgba(255,255,255,0.35);margin:10px auto;width:32px"></div>
      <div style="font-size:{gs}px;color:rgba(255,255,255,0.85);font-weight:700;
                  letter-spacing:0.3px;word-break:break-word;line-height:1.4">{name}</div>
    </td>
    <td style="padding:16px 18px;vertical-align:top;border:1px solid #e8e8e8;border-left:none">
      {right_title}{right_co}{right_tag}
      <div style="font-size:{cs}px;color:#555;line-height:1.9">{contact_block}</div>
    </td>
  </tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 7. ELEGANT — double top rule, generous spacing, refined typography
    # ════════════════════════════════════════════════════════════════════════
    elif tpl == 'elegant':
        tc_html = (f'<div style="font-size:{ts}px;color:#777;font-weight:500;margin-top:3px;'
                   f'letter-spacing:0.2px">{title_company}</div>') if title_company else ''
        tag_html = (f'<div style="font-size:{gs}px;color:#bbb;font-style:italic;'
                    f'margin-top:5px;letter-spacing:0.3px;line-height:1.5">{tagline}</div>') if tagline else ''
        soc_html = (f'<div style="margin-top:4px;font-size:{cs}px">{social_row}</div>') if social_row else ''
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:480px;margin:0">
  <tr><td style="border-top:3px solid {accent};padding-top:0;font-size:0">&nbsp;</td></tr>
  <tr><td style="border-top:1px solid {accent};padding-top:0;font-size:0">&nbsp;</td></tr>
  <tr>
    <td style="padding:12px 0 10px">
      <div style="font-size:{ns}px;font-weight:700;color:#1a1a1a;letter-spacing:-0.2px;line-height:1.2">{name}</div>
      {tc_html}
      {tag_html}
    </td>
  </tr>
  <tr>
    <td style="padding-top:10px;font-size:{cs}px;color:#777;line-height:1.9;border-top:1px solid #f0f0f0">
      {contact_row}
      {soc_html}
    </td>
  </tr>
  <tr><td style="padding-top:12px;border-top:1px solid {accent};font-size:0">&nbsp;</td></tr>
  <tr><td style="border-top:3px solid {accent};padding-top:0;font-size:0">&nbsp;</td></tr>
</table>'''

    # ════════════════════════════════════════════════════════════════════════
    # 8. CARD — full outer border, accent header, footer social strip
    # ════════════════════════════════════════════════════════════════════════
    else:  # card
        tc_html = (f'<div style="font-size:{ts}px;color:rgba(255,255,255,0.85);'
                   f'margin-top:2px;font-weight:500">{title}</div>') if title else ''
        contact_left = ''.join([
            f'<div style="margin-bottom:4px">{email_link}</div>' if email_link else '',
            f'<div style="margin-bottom:4px;color:#555">{phone}</div>' if phone else '',
            f'<div>{website_link}</div>' if website_link else '',
        ])
        right_block = ''.join([
            f'<div style="font-size:{gs}px;color:#aaa;font-style:italic;margin-bottom:7px;line-height:1.5">{tagline}</div>' if tagline else '',
            f'<div style="font-size:{ts - 1}px;color:{accent};font-weight:600">{company}</div>' if company else '',
        ])
        footer = (f'<tr><td colspan="2" style="background:{accent_light};padding:8px 16px;'
                  f'border-top:1px solid #ebebeb;font-size:{cs}px">{social_row}</td></tr>') if social_row else ''
        return f'''<table cellpadding="0" cellspacing="0" style="font-family:{font_stack};border-collapse:collapse;max-width:500px;margin:0;border:1px solid #e2e2e2">
  <tr>
    <td colspan="2" style="background:{accent};padding:12px 16px 11px">
      <div style="font-size:{ns}px;font-weight:800;color:#fff;letter-spacing:-0.3px;line-height:1.2">{name}</div>
      {tc_html}
    </td>
  </tr>
  <tr>
    <td style="padding:12px 12px 12px 16px;font-size:{cs}px;color:#444;vertical-align:top;
               line-height:1.9;border-right:1px solid #f0f0f0;min-width:170px">
      {contact_left}
    </td>
    <td style="padding:12px 16px 12px 12px;font-size:{cs}px;vertical-align:top;line-height:1.9">
      {right_block}
    </td>
  </tr>
  {footer}
</table>'''


# ── Routes ────────────────────────────────────────────────────────────────
@bp.route('/')
def index():
    return render_template('email_sig/index.html')


@bp.route('/ai-tagline', methods=['POST'])
def ai_tagline():
    if not get_groq_key():
        return jsonify({'error': get_t()['email_no_groq']})

    data = request.get_json() or {}
    name    = data.get('name', '')
    title   = data.get('title', '')
    company = data.get('company', '')
    style   = data.get('style', 'professional')

    prompt = (
        f"Generate a single short professional email signature tagline (max 12 words) for "
        f"{name or 'a professional'}, {title or 'a professional'}"
        f"{' at ' + company if company else ''}. "
        f"Style: {style}. "
        "Return ONLY the tagline text, no quotes, no explanation."
    )
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=60,
            temperature=0.8,
        )
        tagline = response.choices[0].message.content.strip().strip('"').strip("'")
        return jsonify({'tagline': tagline})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/render-preview', methods=['POST'])
def render_preview():
    data = request.get_json() or {}
    html = build_signature_html(
        name=data.get('name', ''),
        title=data.get('title', ''),
        company=data.get('company', ''),
        email=data.get('email', ''),
        phone=data.get('phone', ''),
        website=data.get('website', ''),
        linkedin=data.get('linkedin', ''),
        twitter=data.get('twitter', ''),
        tagline=data.get('tagline', ''),
        accent_color=data.get('accent_color', '#a855f7'),
        font=data.get('font', 'Arial, sans-serif'),
        template=data.get('template', 'modern'),
        font_size=data.get('font_size', 'medium'),
    )
    return jsonify({'html': html})


@bp.route('/export.html')
def export_html():
    args = request.args
    sig_html = build_signature_html(
        name=args.get('name', ''),
        title=args.get('title', ''),
        company=args.get('company', ''),
        email=args.get('email', ''),
        phone=args.get('phone', ''),
        website=args.get('website', ''),
        linkedin=args.get('linkedin', ''),
        twitter=args.get('twitter', ''),
        tagline=args.get('tagline', ''),
        accent_color=args.get('accent_color', '#a855f7'),
        font=args.get('font', 'Arial, sans-serif'),
        template=args.get('template', 'modern'),
        font_size=args.get('font_size', 'medium'),
    )
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Email Signature</title>
</head>
<body style="margin:48px;font-family:Arial,sans-serif;background:#fafafa">
  <p style="color:#aaa;font-size:12px;margin-bottom:28px">
    Copy the signature below and paste it into your email client's signature editor.
  </p>
  <div style="background:#fff;padding:32px;display:inline-block;border-radius:8px">
    {sig_html}
  </div>
</body>
</html>"""
    return Response(
        full_html,
        mimetype='text/html',
        headers={'Content-Disposition': 'attachment; filename="email-signature.html"'}
    )
