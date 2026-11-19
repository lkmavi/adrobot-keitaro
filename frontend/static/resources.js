const resourceDialog = document.querySelector('#resource-dialog');
const resourceForm = document.querySelector('#resource-form');
const resourceInfo = {
  group: ['Новая группа', 'Префикс добавится автоматически, пробелы станут подчёркиваниями.', 'Название группы'],
  domain: ['Добавить домен', 'Укажите существующий домен. DNS настраивается отдельно.', 'Имя домена'],
  source: ['Новый источник', 'Дополнительные параметры можно настроить в Keitaro.', 'Название источника'],
  offer: ['Новый оффер', 'Создаётся внешний оффер с указанным адресом назначения.', 'Название оффера'],
};
let resourceTarget = null;

function showResourceMessage(container, message, isError = false) {
  let status = container.querySelector('.resource-status');
  if (!status) {
    status = document.createElement('small');
    status.className = 'resource-status';
    status.setAttribute('role', 'status');
    container.append(status);
  }
  status.textContent = message;
  status.classList.toggle('resource-status-error', isError);
}

async function refreshResource(select, preferredId = select.value) {
  const response = await fetch(`/resources/options/${encodeURIComponent(select.dataset.resource)}`, {cache: 'no-store'});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Не удалось обновить список');
  const placeholder = select.options[0].cloneNode(true);
  select.replaceChildren(placeholder);
  for (const item of result.options) {
    select.add(new Option(`${item.id} · ${item.name}`, String(item.id)));
  }
  const found = [...select.options].some(option => option.value === String(preferredId));
  select.value = found ? String(preferredId) : '';
  return found;
}

document.querySelectorAll('[data-refresh-resource]').forEach(button => {
  button.addEventListener('click', async () => {
    const container = button.closest('.field');
    const select = container.querySelector('select');
    const previous = select.value;
    button.disabled = true;
    try {
      const retained = await refreshResource(select);
      showResourceMessage(container, previous && !retained ? 'Выбранный ресурс больше не найден. Выберите другой.' : 'Список обновлён');
    } catch (error) {
      showResourceMessage(container, error.message || 'Ошибка обновления', true);
    } finally { button.disabled = false; }
  });
});

document.querySelectorAll('[data-create-resource]').forEach(button => {
  button.addEventListener('click', () => {
    const kind = button.dataset.createResource;
    resourceTarget = button.closest('.field').querySelector('select');
    resourceForm.reset();
    resourceForm.elements.kind.value = kind;
    resourceDialog.querySelector('#resource-dialog-title').textContent = resourceInfo[kind][0];
    resourceDialog.querySelector('#resource-dialog-description').textContent = resourceInfo[kind][1];
    resourceDialog.querySelector('#resource-name-label').textContent = resourceInfo[kind][2];
    const urlField = resourceDialog.querySelector('#resource-url-field');
    urlField.hidden = kind !== 'offer';
    resourceForm.elements.url.required = kind === 'offer';
    resourceDialog.querySelector('.dialog-error').hidden = true;
    resourceDialog.showModal();
    resourceForm.elements.name.focus();
  });
});
resourceDialog?.querySelectorAll('.dialog-close, .dialog-cancel').forEach(button => button.addEventListener('click', () => resourceDialog.close()));

resourceForm?.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = resourceForm.querySelector('[type=submit]');
  const errorBox = resourceDialog.querySelector('.dialog-error');
  errorBox.hidden = true;
  submit.disabled = true;
  try {
    const response = await fetch('/resources/inline', {method: 'POST', body: new FormData(resourceForm)});
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 403) {
        const kind = resourceForm.elements.kind.value;
        document.querySelectorAll(`[data-create-resource="${kind}"]`).forEach(button => {
          const note = document.createElement('small');
          note.className = 'permission-note';
          note.textContent = 'Создание недоступно для текущего ключа';
          button.replaceWith(note);
        });
      }
      throw new Error(result.error || 'Не удалось создать ресурс');
    }
    try {
      const found = await refreshResource(resourceTarget, result.id);
      showResourceMessage(resourceTarget.closest('.field'), found ? 'Ресурс создан и выбран' : `Ресурс создан (ID ${result.id}), но пока не появился в списке. Обновите его.`);
    } catch {
      showResourceMessage(resourceTarget.closest('.field'), `Ресурс создан (ID ${result.id}), но список не обновился. Обновите его вручную.`, true);
    }
    resourceDialog.close();
  } catch (error) {
    errorBox.textContent = error.message || 'Ошибка создания ресурса';
    errorBox.hidden = false;
  } finally { submit.disabled = false; }
});
