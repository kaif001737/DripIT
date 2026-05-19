from pathlib import Path
import os
import smtplib
from email.message import EmailMessage

from flask import Flask, abort, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["SMTP_HOST"] = os.getenv("SMTP_HOST", "smtp.gmail.com")
app.config["SMTP_PORT"] = int(os.getenv("SMTP_PORT", "587"))
app.config["SMTP_USER"] = os.getenv("SMTP_USER", "dripitcontact@gmail.com")
app.config["SMTP_PASSWORD"] = os.getenv("SMTP_PASSWORD", "gvle cabt jaka zuaf")
app.config["ADMIN_EMAIL"] = os.getenv("ADMIN_EMAIL", "dripitcontact@gmail.com")
app.config["MAIL_LOGO_PATH"] = os.getenv(
    "MAIL_LOGO_PATH", str(Path(app.static_folder) / "images" / "logo.jpg")
)
COLLECTION_DIR = "images"
IMAGE_ROOT = Path(app.static_folder) / COLLECTION_DIR
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp"}
DEFAULT_COLLECTION_CATEGORIES = ["baggy", "Clogs", "Sandals", "T-shirts"]
CATEGORY_DISPLAY_NAMES = {
    "baggy": "Baggy Pant",
    "clogs": "Clogs",
    "sandals": "Sandals",
    "t-shirts": "T-shirts",
}


def _display_name_for_category(raw_name: str):
    return CATEGORY_DISPLAY_NAMES.get(raw_name.lower(), raw_name)


def _smtp_password():
    return app.config["SMTP_PASSWORD"].replace(" ", "").strip()


def _send_contact_emails(admin_message: EmailMessage, acknowledgement_message: EmailMessage):
    with smtplib.SMTP(app.config["SMTP_HOST"], app.config["SMTP_PORT"], timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(app.config["SMTP_USER"], _smtp_password())
        smtp.send_message(admin_message)
        smtp.send_message(acknowledgement_message)


def _list_images(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
        ],
        key=lambda p: p.name.lower(),
    )


def _collection_categories():
    if not IMAGE_ROOT.exists():
        return []

    categories = []
    for folder in sorted([p for p in IMAGE_ROOT.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        images = _list_images(folder)
        categories.append(
            {
                "name": _display_name_for_category(folder.name),
                "slug": folder.name,
                "count": len(images),
                "preview_url": f"{COLLECTION_DIR}/{folder.name}/{images[0].name}" if images else None,
                "preview_is_external": False,
                "folder_path": f"static/{COLLECTION_DIR}/{folder.name}",
            }
        )

    existing_slugs = {category["slug"].lower() for category in categories}
    for category_name in DEFAULT_COLLECTION_CATEGORIES:
        category_slug = category_name
        if category_slug.lower() in existing_slugs:
            continue
        categories.append(
            {
                "name": _display_name_for_category(category_name),
                "slug": category_slug,
                "count": 0,
                "preview_url": None,
                "preview_is_external": False,
                "folder_path": f"static/{COLLECTION_DIR}/{category_slug}",
            }
        )

    categories.sort(key=lambda c: c["name"].lower())
    return categories


def _attach_inline_logo(email_message: EmailMessage, cid: str = "dripit-logo"):
    logo_path = Path(app.config["MAIL_LOGO_PATH"])
    if not logo_path.exists() or not logo_path.is_file():
        return

    subtype_map = {
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".png": "png",
        ".gif": "gif",
        ".webp": "webp",
    }
    logo_subtype = subtype_map.get(logo_path.suffix.lower())
    if not logo_subtype:
        return

    payload = email_message.get_payload()
    if not isinstance(payload, list) or not payload:
        return

    html_part = None
    for part in reversed(payload):
        if part.get_content_type() == "text/html":
            html_part = part
            break

    if html_part is None:
        return

    with logo_path.open("rb") as logo_file:
        html_part.add_related(
            logo_file.read(),
            maintype="image",
            subtype=logo_subtype,
            cid=f"<{cid}>",
            disposition="inline",
            filename=logo_path.name,
        )


# HOME
@app.route("/")
def home():
    return render_template("index.html", contact_status=request.args.get("contact_status"))

# COLLECTION (KEEP OLD /models)
@app.route("/models")
def models():
    categories = _collection_categories()
    return render_template("models.html", categories=categories)

# ADD THIS ALIAS (THIS FIXES YOUR BUTTON)
@app.route("/collection")
def collection():
    categories = _collection_categories()
    return render_template("models.html", categories=categories)


@app.route("/collection/<category_slug>")
def category_gallery(category_slug):
    categories = _collection_categories()
    selected = next((c for c in categories if c["slug"] == category_slug), None)
    if selected is None:
        abort(404)

    folder = IMAGE_ROOT / selected["slug"]
    images = _list_images(folder)
    image_urls = [
        f"{COLLECTION_DIR}/{selected['slug']}/{img.name}" for img in images
    ]

    return render_template(
        "category_gallery.html",
        category_name=selected["name"],
        category_slug=selected["slug"],
        image_urls=image_urls,
        total_images=len(image_urls),
        collection_dir=COLLECTION_DIR,
    )

# ABOUT
@app.route("/about")
def about():
    return render_template("about.html")

# LOOKBOOK
@app.route("/lookbook")
def lookbook():
    return render_template("lookbook.html")


@app.post("/contact")
def contact_submit():
    name = request.form.get("name", "").strip()
    user_email = request.form.get("email", "").strip()
    mobile_number = request.form.get("mobile_number", "").strip()
    enquiry_type = request.form.get("enquiry_type", "").strip()
    address = request.form.get("address", "").strip()
    message = request.form.get("message", "").strip()

    if not all([name, user_email, mobile_number, enquiry_type, address, message]):
        return redirect(url_for("home", contact_status="invalid", _anchor="contact"))

    if "@" not in user_email or "." not in user_email:
        return redirect(url_for("home", contact_status="invalid", _anchor="contact"))

    admin_message = EmailMessage()
    admin_message["Subject"] = f"New Contact Enquiry ({enquiry_type}) - {name}"
    admin_message["From"] = f"DripIt <{app.config['SMTP_USER']}>"
    admin_message["To"] = app.config["ADMIN_EMAIL"]
    admin_message["Reply-To"] = user_email
    admin_message.set_content(
        "\n".join(
            [
                "New contact enquiry received from DripIt website:",
                "",
                f"Name: {name}",
                f"Email: {user_email}",
                f"Mobile Number: {mobile_number}",
                f"Enquiry Type: {enquiry_type}",
                f"Address: {address}",
                "",
                "Message:",
                message,
            ]
        )
    )
    admin_message.add_alternative(
        f"""
        <html>
          <body style="margin:0; padding:24px; background:#0b0b0b; color:#f5f5f5; font-family:Arial,sans-serif;">
            <div style="max-width:680px; margin:0 auto; border:1px solid #2a2a2a; border-radius:14px; overflow:hidden; background:#111;">
              <div style="padding:18px 22px; border-bottom:1px solid #2a2a2a;">
                <img src="cid:dripit-logo-admin" alt="DripIt" style="height:40px; width:auto; border-radius:6px; vertical-align:middle;">
                <span style="margin-left:10px; font-size:18px; font-weight:700; letter-spacing:0.3px; vertical-align:middle;">DripIt Contact Enquiry</span>
              </div>
              <div style="padding:22px;">
                <p style="margin:0 0 14px; color:#bdbdbd;">A new enquiry was submitted from the website contact section.</p>
                <table style="width:100%; border-collapse:collapse;">
                  <tr><td style="padding:8px 0; color:#9a9a9a; width:170px;">Name</td><td style="padding:8px 0;">{name}</td></tr>
                  <tr><td style="padding:8px 0; color:#9a9a9a;">Email</td><td style="padding:8px 0;">{user_email}</td></tr>
                  <tr><td style="padding:8px 0; color:#9a9a9a;">Mobile Number</td><td style="padding:8px 0;">{mobile_number}</td></tr>
                  <tr><td style="padding:8px 0; color:#9a9a9a;">Enquiry Type</td><td style="padding:8px 0;">{enquiry_type}</td></tr>
                  <tr><td style="padding:8px 0; color:#9a9a9a;">Address</td><td style="padding:8px 0;">{address}</td></tr>
                </table>
                <div style="margin-top:16px; padding:14px; border:1px solid #2a2a2a; border-radius:10px; background:#0d0d0d;">
                  <p style="margin:0 0 8px; color:#9a9a9a;">Message</p>
                  <p style="margin:0; line-height:1.7;">{message}</p>
                </div>
              </div>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )
    _attach_inline_logo(admin_message, cid="dripit-logo-admin")

    acknowledgement_message = EmailMessage()
    acknowledgement_message["Subject"] = "Thank you for contacting DripIt"
    acknowledgement_message["From"] = f"DripIt <{app.config['SMTP_USER']}>"
    acknowledgement_message["To"] = user_email
    acknowledgement_message.set_content(
        "\n".join(
            [
                f"Hi {name},",
                "",
                "Thank you for contacting DripIt Clothing.",
                "We have successfully received your enquiry.",
                f"Enquiry Type: {enquiry_type}",
                "Our team will respond within 24 hours.",
                "",
                "Warm regards,",
                "DripIt Clothing Team",
            ]
        )
    )
    acknowledgement_message.add_alternative(
        f"""
        <html>
          <body style="margin:0; padding:22px; background:#f3f3f5; color:#111; font-family:Arial,sans-serif;">
            <div style="max-width:680px; margin:0 auto; border:1px solid #e4e4e7; border-radius:18px; overflow:hidden; background:#ffffff;">
              <div style="padding:22px; background:#141414;">
                <table role="presentation" style="border-collapse:collapse;">
                  <tr>
                    <td style="vertical-align:middle;">
                      <img src="cid:dripit-logo-user" alt="DripIt" style="height:46px; width:auto; border-radius:8px; display:block;">
                    </td>
                    <td style="vertical-align:middle; padding-left:10px;">
                      <p style="margin:0; color:#ffffff; font-size:14px; letter-spacing:0.06em; font-weight:700;">DRIP'IT</p>
                      <p style="margin:4px 0 0; color:#d0b06e; font-size:12px;">Premium Clothing Support</p>
                    </td>
                  </tr>
                </table>
              </div>
              <div style="padding:30px 26px;">
                <p style="margin:0 0 14px; color:#1b1b1b; font-size:38px; line-height:1; font-weight:700; letter-spacing:-0.03em;">
                  Hello {name.upper()},
                </p>
                <p style="margin:0 0 14px; line-height:1.75; color:#383838; font-size:17px;">
                  Thank you for contacting <strong>Dripit Clothing</strong>. We have successfully received your request.
                </p>
                <div style="margin:18px 0 16px; padding:16px 18px; border:1px solid #ecebe6; border-radius:14px; background:#f8f8f6;">
                  <table role="presentation" style="width:100%; border-collapse:collapse;">
                    <tr>
                      <td style="padding:4px 0; width:42%; font-size:20px; font-weight:700; color:#212121;">Inquiry Type:</td>
                      <td style="padding:4px 0; font-size:20px; color:#2f2f2f;">{enquiry_type}</td>
                    </tr>
                    <tr>
                      <td style="padding:8px 0 2px; font-size:20px; font-weight:700; color:#212121;">Email:</td>
                      <td style="padding:8px 0 2px; font-size:18px; color:#2f2f2f;">{user_email}</td>
                    </tr>
                  </table>
                </div>
                <p style="margin:0 0 18px; line-height:1.8; color:#3a3a3a; font-size:16px;">
                  Our team will respond within <strong>24 hours</strong>.
                </p>
                <p style="margin:0; line-height:1.7; color:#333; font-size:16px;">
                  Warm Regards,<br><strong>Dripit Clothing Team</strong>
                </p>
              </div>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )
    _attach_inline_logo(acknowledgement_message, cid="dripit-logo-user")

    try:
        _send_contact_emails(admin_message, acknowledgement_message)
    except Exception as exc:
        app.logger.exception("Contact form email failed: %s", exc)
        return redirect(url_for("home", contact_status="error", _anchor="contact"))

    return redirect(url_for("home", contact_status="success", _anchor="contact"))


# 404 HANDLER
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)