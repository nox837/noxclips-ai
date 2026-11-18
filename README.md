# NoxClips.ai v2

A mobile-friendly AI clipping studio prototype. The frontend accepts YouTube links only and provides clip settings, aspect-ratio choices, and caption-template selection.

## Project status
- [x] Responsive interface
- [x] YouTube URL format validation
- [x] Three clips / 30 seconds defaults
- [x] Nine clipping-style choices
- [x] Aspect-ratio choices
- [x] Caption template and font controls
- [ ] Authorized video ingestion
- [ ] AI moment detection and ranking
- [ ] FFmpeg clip rendering
- [ ] Face/speaker tracking
- [ ] Preview and export pipeline

**Important:** This is a starter interface and API scaffold, not yet a working automatic clip generator. YouTube URL validation does not grant permission or provide access to video streams. Configure an authorized source for videos you own or have permission to edit, then connect a background processing worker.
