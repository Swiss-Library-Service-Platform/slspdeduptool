document.querySelectorAll('form[data-confirm-delete]').forEach(form => {
  form.addEventListener('submit', event => {
    const primary_id = form.elements.delete_primary_id.value;
    if (!window.confirm('Delete ' + primary_id + ' ?')) {
      event.preventDefault();
    }
  });
});
