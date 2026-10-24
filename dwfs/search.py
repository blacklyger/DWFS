from flask          import Blueprint, request, url_for, jsonify
from .models        import Media
from flask_login    import login_required, current_user
from .              import main
from .security      import segments_from_url, user_subject_path

search = Blueprint("search", __name__)


def like_pattern(query):
    """
    Build a fuzzy LIKE pattern ("abc" -> "%a%b%c%"). LIKE wildcards in the user
    input are escaped. The value is passed as bound parameter by SQLAlchemy,
    so the query itself is never built from user input (no SQL injection).
    """
    escaped = [c.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for c in query]
    return f"%{'%'.join(escaped)}%"


def search_query(query, subject, path):

    if not query:
        return jsonify([])

    main.require_subject(subject)
    segments = segments_from_url(path, subject)

    sres = Media.query.filter_by(
        name=current_user.username,
        subject=subject
    ).filter(
        Media.filename.ilike(like_pattern(query[:100]), escape="\\")
    )

    # Inside a folder only search that folder, on the subject page search everything.
    if segments:
        sres = sres.filter_by(path=str(user_subject_path(current_user.username, subject, *segments)))

    ret = []
    for item in sres.limit(200).all():

        r = {
            "filename": item.filename,
            "category": item.category,
            "unique_id": item.unique_id,
            "is_dir": item.is_dir(),
        }

        if item.is_dir():
            r["url"]          = main.create_url_from_media_path(item.path, item.filename)
            r["download_url"] = url_for('share.share_folder', username=current_user.username, subject=subject, folder_name=item.filename, folder_uid=item.unique_id, _external=True)
        else:
            r["file_size"]    = main.calc_file_size(item.path, item.filename)
            r["download_url"] = url_for('main.download_file', uid=item.unique_id, _external=True)

        ret.append(r)

    return jsonify(ret)

@search.route("/search_query", methods=["POST"])
@login_required
def search_data():

    value           = request.form.get("value")
    current_subject = request.form.get("current_subject")
    path            = request.form.get("path")

    return search_query(query=value, subject=current_subject, path=path)
