// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://shlok-bhakta.github.io',
	base: '/3d-modeling-thingy-ios',
	publicDir: '../docs-media',
	integrations: [
		starlight({
			title: '3D Modeling Thingy',
			description: 'Install and use 3D Modeling Thingy, an independent Blender-based app for iPhone and iPad.',
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/Shlok-Bhakta/3d-modeling-thingy-ios',
				},
			],
			sidebar: [
				{ label: 'Start here', items: [{ label: 'Overview', slug: 'index' }, { label: 'Install', slug: 'install' }] },
				{
					label: 'Controls',
					items: [
						{ label: 'Touch and gestures', slug: 'controls/touch' },
						{ label: 'Short video guide', slug: 'controls/video-guide' },
						{ label: 'Keyboard, mouse, and Pencil', slug: 'controls/keyboard-mouse-pencil' },
					],
				},
				{
					label: 'Workflows',
					items: [
						{ label: 'Files and windows', slug: 'workflow/files-and-windows' },
						{ label: 'Rendering', slug: 'workflow/rendering' },
					],
				},
				{ label: 'Reference', items: [{ label: 'What is different', slug: 'what-is-different' }, { label: 'Known limitations', slug: 'limitations' }] },
			],
		}),
	],
});
