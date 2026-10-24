function do_it(it) {
    for (i = 0; i < all.length; i++) {
        element = document.getElementById(all[i]);

        if (element.id != it.id) {
            if (element.classList[0] == 'is-active') {
                element.classList.remove('is-active');
            }
        }
    }

    it.classList.add('is-active');

    for (y = 0; y < all_columns.length; y++) {
        if (all_columns[y].startsWith(it.id)) {
            document.getElementById(all_columns[y]).style.display = "block";
        }
        else {
            document.getElementById(all_columns[y]).style.display = "none";
        }
    }

}


// Escape every value that is inserted into the DOM as HTML (prevents XSS).
function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


function open_modal(modal_name) {
    document.getElementById(modal_name).classList.add('is-active');
}


function close_modal(modal_name) {
    document.getElementById(modal_name).classList.remove('is-active');
}

function get_all_files() {
    var data = document.getElementById('fileupload').files;
    var file_data = '';

    file_data += '<thead>';
    file_data += '<tr>';
    file_data += '<th><abbr title="File_ID">ID</abbr></th>';
    file_data += '<th><abbr title="Filename">Dateiname</abbr></th>';
    file_data += '</tr>';
    file_data += '</thead>';

    $.each(data, function (key, value) {
        key += 1;

        file_data += '<tbody>';
        file_data += '<tr>';
        file_data += '<td>' + key + '</td>';
        file_data += '<td>' + escapeHtml(value.name) + '</td>';
        file_data += '</tr>';
        file_data += '</tbody>';
    });

    $('#filetable').html(file_data);
}


function roundTo(number, decimal_places) {
    let p = Math.pow(10, decimal_places);
    return Math.round(number * p) / p;
}

function postFile() {

    // TODO: Check if file extension is allowed BEFORE uploading the file
    var formData = new FormData();

    var files = $('#fileupload')[0].files;

    for (i = 0; i < files.length; i++) {
        formData.append(`file_${i}`, files[i]);
    }

    formData.append('current_subject', $('#current_subject').val());
    formData.append('file_path', $('#file_path').val());

    $.ajax({
        xhr: function () {
            var xhr = new XMLHttpRequest();

            var lTime = new Date().getTime();
            var lastMB = 0;

            xhr.upload.addEventListener("progress", function (evt) {

                if (evt.lengthComputable) {
                    var now = new Date().getTime();
                    var percentComplete = evt.loaded / evt.total;
                    percentComplete = parseInt(percentComplete * 100);
                    $('#upload_progress').val(percentComplete);

                    var bytes = evt.loaded;
                    var total = evt.total;
                    var MB = bytes / 1000000;
                    var uploadedMB = MB - lastMB;
                    var elapsed = (now - lTime) / 1000;
                    var mbps = elapsed ? roundTo((uploadedMB / elapsed) * 8, 2) : 0;
                    lastMB = MB;
                    lTime = now;


                    $('#progress_label').text(`${percentComplete}% [${roundTo(evt.loaded / 1000000, 2)} MB of ${roundTo(evt.total / 1000000, 2)} MB with ${mbps} MBit/s (${roundTo(mbps / 8, 2)} MByte/s)]`);
                }

            }, false);

            return xhr;
        },
        url: "/add_media",
        type: "POST",
        data: formData,
        processData: false,
        contentType: false,
    }).done(function (data) {

        if (data != "OK") {

            $('#upload_error').empty().append($('<div class="notification is-danger has-text-centered"></div>').text(data));

            setTimeout(function () {
                location.reload();
            }, 5000);

            return;
        }

        $('#progress_label').text("Upload complete!");

        setTimeout(function () {
            location.reload();
        }, 2000);

    }).fail(function (xhr) {
        $('#upload_error').empty().append($('<div class="notification is-danger has-text-centered"></div>')
            .text(xhr.status == 413 ? "Die Datei ist zu groß." : "Upload fehlgeschlagen."));
    });
}

function check(source) {
    checkboxes = document.getElementsByName('media_to_remove');
    for (var i = 0, n = checkboxes.length; i < n; i++) {
        checkboxes[i].checked = source.checked;
    }
}

function copy_link(it) {

    var el = document.createElement('input');
    el.value = it.innerHTML;
    el.setAttribute('hidden', '');
    el.style = { position: 'absolute', left: '-9999px' };
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
}

$(function () {

    var ctoken = $("#ctoken").val();

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", ctoken)
            }
        }
    })

    $("a#regenerate_button").on('click', function (e) {

        checkBoxes = document.getElementsByName('media_to_remove');
        to_change = [];

        for (i = 0; i < checkBoxes.length; i++) {
            if (checkBoxes[i].checked) {
                to_change.push(checkBoxes[i].value);
            }
        }

        $.ajax({
            method: "POST",
            url: "/regenerate_uids",
            data: {
                current_subject: $("#current_subject").val(),
                current_path: window.location.href,
                change: to_change
            }
        }).done(function (data) {
            if (data == "true") {
                location.reload();
            }
        });
        e.preventDefault();
    });

    $("a#download_files_button").on('click', function (e) {

        e.preventDefault();

        checkBoxes = document.getElementsByName('media_to_remove');
        to_change = [];

        for (i = 0; i < checkBoxes.length; i++) {
            if (checkBoxes[i].checked) {
                to_change.push(checkBoxes[i].value);
            }
        }

        if (to_change.length == 0) {
            return;
        }

        // Regular form POST (incl. CSRF token) so the browser receives the ZIP as download.
        var form = $('<form method="POST" action="/download_files"></form>');
        form.append($('<input type="hidden" name="csrf_token">').val(ctoken));
        form.append($('<input type="hidden" name="current_subject">').val($("#current_subject").val()));
        form.append($('<input type="hidden" name="current_path">').val(window.location.href));

        for (i = 0; i < to_change.length; i++) {
            form.append($('<input type="hidden" name="change[]">').val(to_change[i]));
        }

        form.appendTo('body').submit().remove();
    });

    const params = new URLSearchParams(window.location.search);

    var page = params.get("page");
    var limit = params.get("limit");

    var dropdown_text_page = page ? "Page " + page : "Page 1";
    var dropdown_text_limit = limit ? "Show " + limit + " results" : "Show 10 results";

    $("#current_page_display").text(dropdown_text_page);
    $("#current_limit_display").text(dropdown_text_limit);
    
});

function foreign_access_request(value, folder_uid) {
    $.ajax({
        method: "POST",
        url: "/foreign_access",
        data: {
            value: value,
            folder_uid: folder_uid
        }
    });
}

function send_search_query(value) {

    overview_table = $("#overview_table");
    search_heading = $("#search_heading");
    search_table = $("#search_table");

    search_heading.show();

    if (value == "") {
        overview_table.show();
        search_heading.hide();
        search_table.hide();
    } else {
        overview_table.hide();
        search_heading.html(value);
        search_table.show();
    }

    $.ajax({
        method: "POST",
        url: "/search_query",
        data: {
            value: value,
            current_subject: $("#current_subject").val(),
            path: window.location.href
        }
    }).done(function (l) {

        if (!Array.isArray(l)) {
            return;
        }

        var search_results = "";

        search_results += '<thead>';
        search_results += '<tr>';
        search_results += `<th class='has-text-centered'><abbr title='Typ'>Typ</abbr></th>`;
        search_results += `<th class="has-text-centered"><abbr title="Filename">Name</abbr></th>`;
        search_results += `<th class="has-text-centered"><abbr title="Copy">Download / Teilen</abbr></th>`;
        search_results += `<th class="has-text-centered"><abbr title="Foreign_Access">Fremdzugang</abbr></th>`;
        search_results += `<th class="has-text-centered"><abbr title="Remove">Alle <input type="checkbox" onclick="check(this)"></abbr></th>`;
        search_results += '</tr>';
        search_results += '</thead>';

        for (item of l) {
            search_results += "<tbody>";
            search_results += "<tr>";

            var filename = escapeHtml(item.filename);
            var download_url = escapeHtml(item.download_url);
            var uid = escapeHtml(item.unique_id);

            if (item.is_dir) {
                search_results += `<td><figure class='image is-32x32'><img src="/static/folder.png"></figure></td>`;
                search_results += `<td><a href="${escapeHtml(item.url)}">${filename}</a></td>`;
                search_results += `<td>${download_url}</td>`;
                search_results += `<td class="has-text-centered"><a class="button is-primary" data-uid="${uid}" onclick="foreign_access_request('Ja', this.dataset.uid)">Ja</a>
                                    <a class="button is-danger" data-uid="${uid}" onclick="foreign_access_request('Nein', this.dataset.uid)">Nein</a></td>`;
                search_results += `<td class="has-text-centered">
                <input name="media_to_remove" type="checkbox" value="${filename}">
            </td>`;

            } else {
                search_results += `<td><figure class='image is-32x32'><img src="/static/file.png"></figure></td>`;
                search_results += `<td><a href="${download_url}" target="_blank" rel="noopener">${filename}<br>[${escapeHtml(item.file_size)} MB]</a></td>`;
                search_results += `<td>${download_url}</td>`;
                search_results += "<td class='has-text-centered'>/</td>";
                search_results += `<td class="has-text-centered">
                <input name="media_to_remove" type="checkbox" value="${filename}">
                </td>`;
            }

            search_results += "</tr>";
            search_results += "</tbody>";
        }

        $("#search_table").html(search_results);

    });
}

function dropdown_trigger(element_id) {
    var dropdown_classlist = document.getElementById(element_id).classList;
    dropdown_classlist.contains("is-active") ? dropdown_classlist.remove("is-active") : dropdown_classlist.add("is-active");
}
