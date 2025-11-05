(function() {
    const SELECTOR = '.custom-select';

    function closestForm(element) {
        return element ? element.closest('form') : null;
    }

    function getOptionLabel(optionEl, fallback) {
        if (!optionEl) {
            return fallback;
        }
        const textEl = optionEl.querySelector('.select-option-text');
        const label = textEl ? textEl.textContent.trim() : optionEl.textContent.trim();
        return label || fallback;
    }

    function getNativeOptionLabel(select, value, fallback) {
        const nativeOption = Array.from(select.options).find(opt => opt.value === value);
        if (!nativeOption) {
            return fallback;
        }
        return nativeOption.textContent.trim() || fallback;
    }

    function closeAll(except) {
        document.querySelectorAll(SELECTOR).forEach(wrapper => {
            if (wrapper === except) {
                return;
            }
            wrapper.classList.remove('open');
            const trigger = wrapper.querySelector('.select-trigger');
            const dropdown = wrapper.querySelector('.select-dropdown');
            if (trigger) {
                trigger.classList.remove('active');
            }
            if (dropdown) {
                dropdown.classList.remove('show');
            }
        });
    }

    function initCustomSelect(wrapper) {
        if (!wrapper || wrapper.dataset.customSelectInitialized === 'true') {
            return;
        }

        const select = wrapper.querySelector('select');
        const trigger = wrapper.querySelector('.select-trigger');
        const dropdown = wrapper.querySelector('.select-dropdown');

        if (!select || !trigger || !dropdown) {
            return;
        }

        const textEl = trigger.querySelector('.select-text') || trigger;
        const placeholder =
            trigger.dataset.placeholder ||
            wrapper.dataset.placeholder ||
            trigger.getAttribute('data-placeholder') ||
            textEl.textContent.trim();

        const optionElements = Array.from(dropdown.querySelectorAll('.select-option'));

        function syncDisabledState() {
            if (select.disabled) {
                wrapper.classList.add('is-disabled');
            } else {
                wrapper.classList.remove('is-disabled');
            }
        }

        function updateSelectedClasses(value) {
            optionElements.forEach(optionEl => {
                const optionValue = optionEl.dataset.value ?? '';
                optionEl.classList.toggle('selected', optionValue === value);
            });
        }

        function updateTriggerText(value) {
            const matchedOption = optionElements.find(optionEl => {
                const optionValue = optionEl.dataset.value ?? '';
                return optionValue === value && !optionEl.classList.contains('disabled');
            });

            let label = placeholder;
            if (matchedOption) {
                label = getOptionLabel(matchedOption, placeholder);
            } else if (value) {
                label = getNativeOptionLabel(select, value, placeholder);
            }

            if (textEl) {
                textEl.textContent = label;
                textEl.title = label;
            }

            if (!value) {
                trigger.classList.add('placeholder');
            } else {
                trigger.classList.remove('placeholder');
            }
        }

        function applyValue(value, dispatchEvent = false) {
            if (select.value !== value) {
                select.value = value;
            }
            updateSelectedClasses(value);
            updateTriggerText(value);
            if (dispatchEvent) {
                const changeEvent = new Event('change', { bubbles: true });
                select.dispatchEvent(changeEvent);
            }
        }

        function toggleDropdown(event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }

            if (select.disabled) {
                return;
            }

            const isOpen = dropdown.classList.contains('show');
            if (isOpen) {
                closeAll();
                return;
            }

            closeAll(wrapper);
            dropdown.classList.add('show');
            trigger.classList.add('active');
            wrapper.classList.add('open');
        }

        trigger.addEventListener('click', toggleDropdown);

        optionElements.forEach(optionEl => {
            optionEl.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();

                if (optionEl.classList.contains('disabled')) {
                    return;
                }

                const newValue = optionEl.dataset.value ?? '';
                const shouldDispatch = select.value !== newValue;
                applyValue(newValue, shouldDispatch);
                closeAll();

                if (shouldDispatch && wrapper.dataset.autoSubmit === 'true') {
                    const form = closestForm(select);
                    if (form) {
                        form.submit();
                    }
                }
            });
        });

        select.addEventListener('change', () => {
            applyValue(select.value, false);
        });

        const observer = new MutationObserver(() => {
            syncDisabledState();
        });
        observer.observe(select, { attributes: true, attributeFilter: ['disabled'] });

        syncDisabledState();
        applyValue(select.value || '');

        wrapper.dataset.customSelectInitialized = 'true';
    }

    function initAll(root) {
        const scope = root instanceof Element ? root : document;
        scope.querySelectorAll(SELECTOR).forEach(initCustomSelect);
    }

    document.addEventListener('click', event => {
        if (event.target.closest(SELECTOR)) {
            return;
        }
        closeAll();
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeAll();
        }
    });

    document.addEventListener('DOMContentLoaded', () => {
        initAll();
    });

    window.CustomSelect = window.CustomSelect || {
        init: initAll,
        refresh: initAll,
    };
})();
