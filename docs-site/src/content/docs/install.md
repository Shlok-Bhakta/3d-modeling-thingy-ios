---
title: Install 3D Modeling Thingy
description: Download 3D Modeling Thingy and install it on your iPhone or iPad.
---

3D Modeling Thingy requires iOS or iPadOS 18 or newer. The IPA download is about 200 MiB.
The current release still uses the earlier filename, `Blender-iOS.ipa`.

You'll need a sideloading tool to sign the app for your device.
A free Apple Account can be used for signing; you don't need to join Apple's
paid developer program. Free signatures expire after 7 days. Refresh the
signature to keep using the app.

Before installing, read [What doesn't work](/3d-modeling-thingy-ios/limitations/),
especially if you rely on add-ons.

## SideStore

SideStore can install apps and refresh their signatures. We haven't yet
verified the complete install and refresh process through SideStore
on a physical device.

1. Follow SideStore's official [setup requirements](https://docs.sidestore.io/docs/installation/prerequisites)
   and [installation guide](https://docs.sidestore.io/docs/installation/install).
   Initial setup needs a computer, a USB connection, and your Apple Account.
   The guides cover iLoader and LocalDevVPN.
2. Trust the developer app in **Settings > General > VPN & Device Management**
   if asked. Enable **Settings > Privacy & Security > Developer Mode** if needed.
3. Connect LocalDevVPN as described in SideStore's guide.
4. Open the link below in Safari on your device.

[Install with SideStore](sidestore://install?url=https%3A%2F%2Fgithub.com%2FShlok-Bhakta%2F3d-modeling-thingy-ios%2Freleases%2Flatest%2Fdownload%2FBlender-iOS.ipa)

If the link doesn't open SideStore, download the IPA and select it from
SideStore's **My Apps** tab.

After installation, check the app's expiry in **My Apps**. Try refreshing it
and make sure the date updates.

[Download the IPA](https://github.com/Shlok-Bhakta/3d-modeling-thingy-ios/releases/latest/download/Blender-iOS.ipa)

## Autoloader

Open the link in Safari on your device. Let Autoloader sign the app, then finish
the installation under **Settings > Installation**.

[Install with Autoloader](https://marginally-better-apps.github.io/Autoloader/?url=https%3A%2F%2Fgithub.com%2FShlok-Bhakta%2F3d-modeling-thingy-ios%2Freleases%2Flatest%2Fdownload%2FBlender-iOS.ipa)

## Other sideloading tools

We haven't verified AltStore or other IPA signers for this release.
If you try one, give it the original `Blender-iOS.ipa` file. Leave the IPA
packaged as downloaded so the tool can sign the app and its bundled libraries.

## First launch

The first launch may take a little longer. Once the app opens, try moving the
startup cube, saving the project, and reopening it.

Keep a copy of your projects outside the app before replacing an installation.
