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

// TODO: Rewrite this, it's fucking horrible!
function open_help_modal() {
    document.getElementById('help_modal').classList.add('is-active');
}

function close_help_modal() {
    document.getElementById('help_modal').classList.remove('is-active');
}

function open_add_modal() {
    document.getElementById("add_subject_modal").classList.add('is-active');
}

function close_add_modal() {
    document.getElementById("add_subject_modal").classList.remove('is-active');
}

function open_rename_modal() {
    document.getElementById("rename_subject_modal").classList.add('is-active');
}

function close_rename_modal() {
    document.getElementById("rename_subject_modal").classList.remove('is-active');
}

function open_rename_file_modal() {
    document.getElementById("rename_file_modal").classList.add("is-active");
}

function close_rename_file_modal() {
    document.getElementById("rename_file_modal").classList.remove("is-active");
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
        console.log(key, value.name);
        key += 1;

        file_data += '<tbody>';
        file_data += '<tr>';
        file_data += '<td>' + key + '</td>';
        file_data += '<td>' + value.name + '</td>';
        file_data += '</tr>';
        file_data += '</tbody>';
    });

    $('#filetable').html(file_data);
}

function copy_link(it) {
    
    var el = document.createElement('input');
    el.value = it.innerHTML;
    el.setAttribute('hidden', '');
    el.style = {position: 'absolute', left: '-9999px'};
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
}

/*
function lolly() {

    var ctoken = $("#ctoken").val();

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", ctoken)
            }
        }
    })

    $.ajax({
        method: "POST",
        url: "/lollypop",
        data: {
            word: $("#haha").val()
        }
    });
}
*/