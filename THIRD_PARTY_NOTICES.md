# Third-party notices

`build-manim-decks` is original orchestration, validation, QA, and export code built
on separately licensed open-source tools. Their source code and binaries are not
vendored in this repository. Installing or bundling dependencies does not place them
under this repository's MIT license.

## Runtime and development dependencies

| Project | Use | License and copyright | Upstream |
|---|---|---|---|
| Manim Community Edition | Animation and rendering | MIT; Copyright (c) 2018 3Blue1Brown LLC and Copyright (c) 2024 Manim Community Developers | https://github.com/ManimCommunity/manim |
| Manim Slides | Slide manifests and PPTX/PDF conversion | MIT; Copyright (c) 2022-2024 Jérome Eertmans | https://github.com/jeertmans/manim-slides |
| PyYAML | `deck.yaml` parsing | MIT; Copyright (c) 2006-2021 Kirill Simonov, Ingy döt Net, and contributors | https://github.com/yaml/pyyaml |
| Pillow | Image inspection and contact sheets | MIT-CMU; Copyright (c) Secret Labs AB, Fredrik Lundh, Jeffrey A. Clark, and contributors | https://github.com/python-pillow/Pillow |
| pypdf | PDF text/image extraction and structural verification | BSD-3-Clause; Copyright (c) Mathieu Fenniak and contributors | https://github.com/py-pdf/pypdf |
| python-pptx | PowerPoint support used by Manim Slides | MIT; Copyright (c) 2013 Steve Canny | https://github.com/scanny/python-pptx |
| pytest | Development tests | MIT; Copyright (c) 2004 Holger Krekel and others | https://github.com/pytest-dev/pytest |
| FFmpeg | External video/frame command-line tools | LGPL-2.1-or-later or GPL-2.0-or-later, depending on build | https://ffmpeg.org/legal.html |

LaTeX and system fonts are optional external tools. They are not distributed by this
repository and must be reviewed under the licenses of the user's chosen distribution.
This source notice covers direct and workflow-relevant components. A binary bundle,
container, or installer must inventory and preserve notices for every transitive and
system dependency actually included.

## Writing-review methodology

The text-review workflow was independently implemented for this skill, with
methodological inspiration from the following projects. No upstream skill file is
vendored.

- Humanizer, MIT, Copyright (c) 2025 Siqi Chen:
  https://github.com/blader/humanizer
- Humanizer-zh, MIT, Copyright (c) 2026 歸藏:
  https://github.com/op7418/Humanizer-zh
- Stop Slop, MIT, by Hardik Pandya:
  https://github.com/hardikpandya/stop-slop
- Wikipedia's “Signs of AI writing,” the upstream reference used by those projects:
  https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing

Wikimedia text is generally available under CC BY-SA 4.0 and GFDL. This repository
does not reproduce the Wikipedia article; it uses independently worded review rules.

## Non-bundled proprietary assets

The project may name Microsoft YaHei or another locally installed font. No Microsoft
font file is included. Generated bitmap/video output and font redistribution have
different terms; never add `.ttf`, `.otf`, `.ttc`, or similar proprietary font files
to a release without explicit redistribution rights.
