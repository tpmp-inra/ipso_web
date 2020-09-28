function start_long_task() {
    // add task status elements
    $('#progress-header').text("Executing jobs");
    $('#back-cancel').text("< Back, cancels task in progress");
    document.getElementById("start-bg-job").className = ("btn btn-primary disabled");

    // send ajax POST request to start background job
    $.ajax({
        type: 'POST',
        url: '/init_queue',
        success: function (data, status, request) {
            status_url = request.getResponseHeader('Location');
            update_progress(status_url);
        },
        error: function () {
            alert('Unexpected error');
        }
    });
}

function update_progress(status_url) {
    // send GET request to status URL
    $.getJSON(status_url, function (data) {
        // update UI
        if ('current' in data) {
            percent = parseInt(data.current * 100 / data.total);
            pb = document.getElementById("progress-bar").style.width = percent + "%";
            document.getElementById("progress-label").innerHTML = percent + '% - ' + data['current'] + '/' + data['total'];
        }
        if (data.state != 'PENDING' && data.state != 'PROGRESS') {
            if ('result' in data) {
                // show result
                $('#progress-header').text('Result: ' + data.result);
            } else {
                // something unexpected happened
                $('#progress-header').text('Result: ' + data.state);
            }
            $('#back-cancel').text("< Back");
            document.getElementById("start-bg-job").className = ("btn btn-primary active");
        } else {
            // rerun in 2 seconds
            setTimeout(function () {
                update_progress(status_url);
            }, 2000);
        }
    });
}