<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { onMount, getContext } from 'svelte';

	const i18n = getContext('i18n');

	import { getPromptByCommand, updatePromptById } from '$lib/apis/prompts';
	import { page } from '$app/stores';

	import PromptEditor from '$lib/components/workspace/Prompts/PromptEditor.svelte';

	let prompt = null;
	let disabled = false;

	const onSubmit = async (_prompt) => {
		console.log(_prompt);
		const prompt = await updatePromptById(localStorage.token, _prompt).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (prompt) {
			toast.success($i18n.t('Prompt updated successfully'));
			await goto('/workspace/prompts');
		}
	};

	onMount(async () => {
		const command = $page.url.searchParams.get('command');
		if (command) {
			const _prompt = await getPromptByCommand(
				localStorage.token,
				command.replace(/\//g, '')
			).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (_prompt) {
				disabled = !_prompt.write_access ?? true;
				prompt = {
					id: _prompt.id,
					name: _prompt.name,
					command: _prompt.command,
					content: _prompt.content,
					tags: _prompt.tags,
					access_grants: _prompt?.access_grants === undefined ? [] : _prompt?.access_grants
				};
			} else {
				goto('/workspace/prompts');
			}
		} else {
			goto('/workspace/prompts');
		}
	});
</script>

{#if prompt}
	<PromptEditor {prompt} {onSubmit} {disabled} edit />
{/if}
