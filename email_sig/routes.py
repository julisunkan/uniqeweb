import os
from flask import Blueprint, render_template, request, jsonify, Response
from groq import Groq
from config import get_groq_key

bp = Blueprint('email_sig', __name__, template_folder='templates')


def get_groq_client():
    key = get_groq_key()
    if not key:
        raise ValueError('GROQ_API_KEY not set. Configure it in Admin → API Keys.')
    return Groq(api_key=key)


def build_signature_html(name, title, company, email, phone, website, linkedin,
                          twitter, tagline, accent_color, font, template):
    accent = accent_color or '#a855f7'
    font_stack = f"{font}, Arial, sans-serif" if font else "Arial, sans-serif"

    # Build contact parts
    email_link = f'<a href="mailto:{email}" style="color:#555;text-decoration:none">{email}</a>' if email else ''
    website_link = f'<a href="{website}" style="color:#555;text-decoration:none">{website}</a>' if website else ''

    contact_parts = []
    if email_link:
        contact_parts.append(email_link)
    if phone:
        contact_parts.append(f'<span>{phone}</span>')
    if website_link:
        contact_parts.append(website_link)

    contact_row = ' &nbsp;·&nbsp; '.join(contact_parts)

    social_parts = []
    if linkedin:
        handle = linkedin.rstrip('/').split('/')[-1]
        social_parts.append(
            f'<a href="{linkedin}" style="color:{accent};text-decoration:none">in/{handle}</a>'
        )
    if twitter:
        tw = twitter.lstrip('@')
        social_parts.append(
            f'<a href="https://twitter.com/{tw}" style="color:{accent};text-decoration:none">@{tw}</a>'
        )
    social_row = ' &nbsp;·&nbsp; '.join(social_parts)

    tpl = (template or 'modern').lower()

    if tpl == 'modern':
        html = f'''<table style="font-family:{font_stack};border-collapse:collapse;max-width:480px;margin:0;padding:0">
  <tr>
    <td style="border-left:4px solid {accent};padding-left:12px;padding-top:4px;padding-bottom:4px">
      <strong style="font-size:16px;color:#1a1a1a;display:block">{name}</strong>
      <span style="color:{accent};font-size:13px;display:block">{title}{' at ' + company if company else ''}</span>
      {f'<span style="color:#666;font-size:12px;font-style:italic;display:block">{tagline}</span>' if tagline else ''}
    </td>
  </tr>
  <tr>
    <td style="padding-top:8px;font-size:12px;color:#555;border-left:4px solid transparent;padding-left:12px">
      {contact_row}
      {f'<br>{social_row}' if social_row else ''}
    </td>
  </tr>
</table>'''

    elif tpl == 'classic':
        name_display = name or ''
        title_display = f"{title}{' — ' + company if company else ''}" if title else company or ''
        html = f'''<table style="font-family:{font_stack};border-collapse:collapse;max-width:480px;margin:0;padding:0">
  <tr>
    <td colspan="2" style="background:{accent};padding:8px 14px;border-radius:4px 4px 0 0">
      <strong style="font-size:16px;color:#ffffff">{name_display}</strong>
      {f'<span style="color:rgba(255,255,255,0.85);font-size:13px;margin-left:10px">{title_display}</span>' if title_display else ''}
    </td>
  </tr>
  <tr>
    <td style="padding:10px 14px;border:1px solid #e5e7eb;border-top:none;border-right:none;font-size:12px;color:#444;vertical-align:top;min-width:200px">
      {f'<div style="margin-bottom:2px">{email_link}</div>' if email_link else ''}
      {f'<div style="margin-bottom:2px">{phone}</div>' if phone else ''}
      {f'<div>{website_link}</div>' if website_link else ''}
    </td>
    <td style="padding:10px 14px;border:1px solid #e5e7eb;border-top:none;border-left:none;font-size:12px;color:#444;vertical-align:top">
      {f'<div style="color:#666;font-style:italic;margin-bottom:6px">{tagline}</div>' if tagline else ''}
      {f'<div>{social_row}</div>' if social_row else ''}
    </td>
  </tr>
</table>'''

    else:  # minimal
        parts = []
        if name:
            parts.append(f'<strong style="color:#1a1a1a">{name}</strong>')
        if title:
            parts.append(f'<span style="color:#555">{title}</span>')
        if company:
            parts.append(f'<span style="color:{accent}">{company}</span>')
        header_line = ' <span style="color:#ccc">|</span> '.join(parts)

        contact_minimal = []
        if email_link:
            contact_minimal.append(email_link)
        if phone:
            contact_minimal.append(phone)
        if website_link:
            contact_minimal.append(website_link)
        if social_row:
            contact_minimal.append(social_row)
        contact_line = ' <span style="color:#ccc">·</span> '.join(contact_minimal)

        html = f'''<table style="font-family:{font_stack};border-collapse:collapse;max-width:520px;margin:0;padding:0">
  <tr>
    <td style="font-size:14px;padding-bottom:4px">{header_line}</td>
  </tr>
  {f'<tr><td style="font-size:11px;color:#888;font-style:italic;padding-bottom:4px">{tagline}</td></tr>' if tagline else ''}
  <tr>
    <td style="font-size:12px;color:#666;border-top:1px solid #e5e7eb;padding-top:6px">{contact_line}</td>
  </tr>
</table>'''

    return html


@bp.route('/')
def index():
    return render_template('email_sig/index.html')


@bp.route('/ai-tagline', methods=['POST'])
def ai_tagline():
    if not get_groq_key():
        return jsonify({'error': 'GROQ_API_KEY not configured. Set it in Admin → API Keys.'})

    data = request.get_json() or {}
    name = data.get('name', '')
    title = data.get('title', '')
    company = data.get('company', '')
    style = data.get('style', 'professional')

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
        font=data.get('font', 'Arial'),
        template=data.get('template', 'modern'),
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
        font=args.get('font', 'Arial'),
        template=args.get('template', 'modern'),
    )
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Email Signature</title>
</head>
<body style="margin:40px;font-family:Arial,sans-serif">
  <p style="color:#888;font-size:12px;margin-bottom:24px">Copy the signature below and paste it into your email client's signature editor.</p>
  {sig_html}
</body>
</html>"""
    return Response(
        full_html,
        mimetype='text/html',
        headers={'Content-Disposition': 'attachment; filename="email-signature.html"'}
    )
