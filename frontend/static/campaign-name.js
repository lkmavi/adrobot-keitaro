const campaignName = document.querySelector('input[name="name"][data-prefix]');
if (campaignName) {
  campaignName.addEventListener('input', () => {
    const prefix = campaignName.dataset.prefix;
    if (prefix && campaignName.value.startsWith(prefix)) {
      campaignName.value = campaignName.value.slice(prefix.length);
    }
  });
}
