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


$(function() {

    var ctoken = $("#ctoken").val();

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", ctoken)
            }
        }
    })

    $("a#regenerate_button").on('click', function(e) {
        $.ajax({
            method: "POST",
            url: "/regenerate_uids",
            data: {
                current_subject: $("#current_subject").val(),
                current_path: window.location.href
            }
        }).done(function(data) {
            if (data == "true") {
                location.reload();
            }
        });
        e.preventDefault();
    });
});