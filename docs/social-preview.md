# Social preview assets

Both images use English copy and the site's black, white, and Cyan palette.

| Use | File | Dimensions | Size |
| --- | --- | --- | --- |
| Website Open Graph and Twitter card | [`og-site.png`](../dist/assets/og-site.png) | 1731 x 909 | 1,461,436 bytes |
| GitHub social preview and README banner | [`og-repository.jpg`](assets/og-repository.jpg) | 1774 x 887 | 155,564 bytes |
| Repository artwork master | [`og-repository.png`](assets/og-repository.png) | 1774 x 887 | 1,374,783 bytes |

The repository JPEG is a quality-90 export of the generated PNG, with its composition and dimensions preserved. It is below GitHub's 1 MB upload limit and has the recommended 2:1 aspect ratio. The website PNG preserves the original generated image.

## Website metadata

`dist/index.html` and `dist/library.html` include English Open Graph and Twitter metadata. The image URL is:

```text
https://motion-lab-archive.bryan131.chatgpt.site/assets/og-site.png
```

This is the reserved hosting origin. It has not been published in this task, so an external social crawler cannot be verified yet. When deploying to another domain, update `og:url`, `og:image`, and `twitter:image` in both HTML files to that deployment's absolute HTTPS URLs. Serve `dist/assets/og-site.png` with the rest of `dist/`.

## GitHub configuration after publication

Committing a README image does not configure the repository's social preview. When the owner is ready to update the remote repository, open **Settings > Social preview > Edit > Upload an image** and choose `docs/assets/og-repository.jpg`. This task only creates a local commit; it does not push, upload the image, or change remote settings.

GitHub recommends a minimum of 640 x 320 pixels, 1280 x 640 for best display, and an image below 1 MB. See the [official social preview instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview). The README uses a relative asset path so it follows the checked-out branch; see [GitHub's relative image path guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes#relative-links-and-image-paths-in-markdown-files).
