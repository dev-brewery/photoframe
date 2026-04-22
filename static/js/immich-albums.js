/**
 * Immich Album Picker - Fully Self-Contained
 *
 * This file dynamically injects ALL UI elements (Browse button + modal).
 * No changes required to main.html or main.js.
 *
 * Extension point: Any service implementing hasAlbumPicker() returning True
 * and providing a discoverAlbums() method will get the Browse button.
 */

$(document).ready(function() {
    // Inject modal HTML into page (once)
    injectModal();

    // Inject Browse buttons for services with hasAlbumPicker capability
    injectBrowseButtons();
});

/**
 * Inject the album picker modal into the page
 */
function injectModal() {
    if ($('#immich_album_picker').length) return; // Already injected

    var modalHtml =
        '<div class="details" style="display: none" id="immich_album_picker">' +
        '  <div>' +
        '    <h3>Select Album</h3>' +
        '    <input type="text" id="immich_album_search" placeholder="Filter albums..." style="width: 100%">' +
        '    <select id="immich_album_list" size="10" style="width: 100%; margin-top: 10px"></select>' +
        '    <hr>' +
        '    <button id="immich_album_select">Select</button>' +
        '    <button id="immich_album_cancel">Cancel</button>' +
        '    <input type="hidden" id="immich_album_service">' +
        '  </div>' +
        '</div>';

    $('body').append(modalHtml);

    // Bind modal events
    bindModalEvents();
}

/**
 * Fetch service list and inject Browse buttons for services with hasAlbumPicker
 */
function injectBrowseButtons() {
    $.ajax({
        url: '/service/list',
        dataType: 'json'
    }).done(function(services) {
        services.forEach(function(svc) {
            if (svc.hasAlbumPicker) {
                // Find the keyword input row for this service and inject Browse button
                var helpBtn = $('.keyword-help[data-service="' + svc.id + '"]');
                if (helpBtn.length && !helpBtn.siblings('.immich-album-browse').length) {
                    var browseBtn = $('<input type="button" class="immich-album-browse" value="Browse">')
                        .attr('data-service', svc.id);
                    helpBtn.after(browseBtn);
                }
            }
        });
    });
}

/**
 * Bind all modal event handlers
 */
function bindModalEvents() {
    // Browse button click - open modal and fetch albums
    $(document).on('click', '.immich-album-browse', function() {
        var serviceId = $(this).data('service');
        $('#immich_album_service').val(serviceId);
        $('#immich_album_search').val('');
        $('#immich_album_list').empty().append('<option value="">Loading albums...</option>');
        $('#immich_album_picker').show();

        $.ajax({
            url: '/keywords/' + serviceId + '/albums',
            dataType: 'json'
        }).done(function(data) {
            if (data.success && data.albums) {
                populateAlbumList(data.albums);
                $('#immich_album_search').focus();
            } else {
                $('#immich_album_list').empty().append(
                    $('<option>').val('').text('Error: ' + (data.error || 'Unknown error'))
                );
            }
        }).fail(function() {
            $('#immich_album_list').empty().append(
                '<option value="">Error: Could not connect to server</option>'
            );
        });
    });

    // Filter albums as user types
    $(document).on('input', '#immich_album_search', function() {
        var filter = $(this).val().toLowerCase();
        var albums = $('#immich_album_list').data('albums');
        if (!albums) return;

        var filtered = albums.filter(function(album) {
            return album.albumName.toLowerCase().indexOf(filter) !== -1;
        });
        populateAlbumList(filtered);
    });

    // Select button - fill keyword input and close
    $(document).on('click', '#immich_album_select', function() {
        var selected = $('#immich_album_list').val();
        var serviceId = $('#immich_album_service').val();

        if (selected) {
            var browseBtn = $('.immich-album-browse[data-service="' + serviceId + '"]');
            var keywordInput = browseBtn.closest('p').find('.keyword');
            if (keywordInput.length) {
                keywordInput.val(selected);
            }
        }
        $('#immich_album_picker').hide();
    });

    // Double-click album to select immediately
    $(document).on('dblclick', '#immich_album_list', function() {
        $('#immich_album_select').click();
    });

    // Cancel button
    $(document).on('click', '#immich_album_cancel', function() {
        $('#immich_album_picker').hide();
    });

    // Escape key closes modal
    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && $('#immich_album_picker').is(':visible')) {
            $('#immich_album_picker').hide();
        }
    });

    // Enter key in list selects current item
    $(document).on('keydown', '#immich_album_list', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            $('#immich_album_select').click();
        }
    });
}

/**
 * Populate the album dropdown
 */
function populateAlbumList(albums) {
    var select = $('#immich_album_list');
    select.empty();

    if (!albums || albums.length === 0) {
        select.append('<option value="">No albums found</option>');
        return;
    }

    albums.forEach(function(album) {
        var count = album.assetCount || 0;
        var label = album.albumName + ' (' + count + ' photo' + (count !== 1 ? 's' : '') + ')';
        select.append($('<option>').val(album.albumName).text(label));
    });

    // Store for filtering
    select.data('albums', albums);
}
