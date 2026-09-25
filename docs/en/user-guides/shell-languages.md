# Shell languages and project maintenance

Shell translation lets you translate a Mod into a language the game does not offer. For example, Italian text can be displayed through the game's English language option.

**We strongly recommend a separate project for each shell language.** Switching shell languages within one project can mix up saved translations. When the original Mod is updated, Remis may reuse text in the wrong language, leaving you with extra checking and rework.

For example, if a project already contains Italian translations, create another project for Thai instead of switching the same project to Thai. Typing a different name for the same language does not create another set of saved translations. Renaming the language cannot separate translations into different projects.

Create a project from the original Mod using copy import, and include the language in its name. Enable shell translation in the initial translation settings, enter the actual language, select the game's language option and choose an output prefix. For example: Italian, English and `it-`. For another language, create another project without adding the previous translation folders.

You do not need to decide during project creation. A notice appears when you select shell translation, and project management offers an expandable explanation. You can still choose to continue with the same project. Languages officially supported by the game can be maintained together in one project.

Enable both the original Mod and translation Mod in the launcher and select the chosen game language. For Italian using an English shell, select English. Check the result in the game.

Ask the Agent why records can get mixed up if you want more detail. It should explain the practical impact and next step first, then provide storage and update details if requested. Developers can consult the [Agent API reference](../../../.agents/skills/remis-agent/references/api-workflow.md).
