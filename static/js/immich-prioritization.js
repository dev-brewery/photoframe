/**
 * Immich Prioritization UI - Fully Self-Contained
 *
 * This file dynamically injects a prioritization dropdown for Immich services.
 * No changes required to main.html or main.js.
 *
 * Extension point: Any service implementing hasPrioritization() returning True
 * and providing getPrioritization/setPrioritization/getPrioritizationModes methods.
 */

$(document).ready(function() {
    // Inject prioritization dropdowns for services with hasPrioritization capability
    injectPrioritizationDropdowns();
});

/**
 * Fetch service list and inject prioritization dropdown for services with hasPrioritization
 */
function injectPrioritizationDropdowns() {
    $.ajax({
        url: '/service/list',
        dataType: 'json'
    }).done(function(services) {
        services.forEach(function(svc) {
            if (svc.hasPrioritization) {
                injectDropdownForService(svc.id);
            }
        });
    });
}

/**
 * Inject prioritization dropdown for a specific service
 */
function injectDropdownForService(serviceId) {
    // Find the service section and the keyword area
    var keywordHelp = $('.keyword-help').filter(function() {
        return $(this).data('service') === serviceId;
    });
    if (!keywordHelp.length) return;

    // Check if already injected
    var existing = $('.immich-prioritization').filter(function() {
        return $(this).data('service') === serviceId;
    });
    if (existing.length) return;

    // Fetch current prioritization settings
    $.ajax({
        url: '/keywords/' + serviceId + '/prioritization',
        dataType: 'json'
    }).done(function(data) {
        if (!data.success) return;

        // Build dropdown using jQuery element creation
        var select = $('<select class="immich-prioritization">').attr('data-service', serviceId);

        for (var mode in data.modes) {
            var option = $('<option>').val(mode).text(data.modes[mode]);
            if (mode === data.current) {
                option.prop('selected', true);
            }
            select.append(option);
        }

        var wrapper = $('<p class="nospace" style="margin-top: 5px;">')
            .append($('<label style="margin-right: 5px;">').text('Image order:'))
            .append(select);

        // Insert after the keyword input row
        var keywordRow = keywordHelp.closest('p');
        keywordRow.after(wrapper);
    });
}

/**
 * Handle prioritization change
 */
$(document).on('change', '.immich-prioritization', function() {
    var serviceId = $(this).data('service');
    var mode = $(this).val();
    var dropdown = $(this);

    dropdown.prop('disabled', true);

    $.ajax({
        url: '/keywords/' + serviceId + '/prioritization',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ mode: mode }),
        dataType: 'json'
    }).done(function(data) {
        if (data.success) {
            // Brief visual feedback
            dropdown.css('background-color', '#d4edda');
            setTimeout(function() {
                dropdown.css('background-color', '');
            }, 500);
        } else {
            alert('Failed to update prioritization: ' + (data.error || 'Unknown error'));
        }
    }).fail(function() {
        alert('Failed to connect to server');
    }).always(function() {
        dropdown.prop('disabled', false);
    });
});
