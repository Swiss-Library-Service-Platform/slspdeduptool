document.querySelectorAll('input[name="new_barcode"]').forEach(input => {
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      event.preventDefault();
      input.form.submit();
    }
  });
});
