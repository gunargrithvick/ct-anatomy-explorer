# CT Anatomy Explorer v0.5 (14 Oct 2026)

Teaching website: expert organ outlines and AI outlines (VISTA-3D, MONAI) on public CT scans. Not for diagnosis or patient care.

Website: https://gunargrithvick.github.io/ct-anatomy-explorer/

## What is in this release
- 5 CT scans from the TotalSegmentator small dataset (CC BY 4.0)
- 12 organs; Expert, AI and Compare views; Dice and volume table; downloads
- Short teaching notes for each organ, to be checked by faculty

## Results
Results for 10 CT scans (all scans that were run; the website shows 5 of them), v0.5, 14 Oct 2026.
Dice: 1.00 = the AI outline and the expert outline are the same; 0 = no overlap.

| Organ | Scans | Mean Dice | Lowest Dice | Mean volume difference |
|---|---|---|---|---|
| Liver | 10 | 0.97 | 0.95 | 2.2 % |
| Right kidney | 10 | 0.95 | 0.93 | 5.1 % |
| Left kidney | 10 | 0.95 | 0.86 | 4.8 % |
| Spleen | 10 | 0.95 | 0.90 | 4.4 % |
| Aorta | 10 | 0.92 | 0.74 | 8.2 % |
| Urinary bladder | 10 | 0.91 | 0.71 | 13.1 % |
| Oesophagus | 10 | 0.91 | 0.83 | 4.4 % |
| Inferior vena cava | 10 | 0.90 | 0.83 | 2.3 % |
| Stomach | 10 | 0.90 | 0.73 | 11.8 % |
| Pancreas | 10 | 0.84 | 0.73 | 12.7 % |
| Gallbladder | 10 | 0.81 | 0.33 | 16.6 % |
| Duodenum | 10 | 0.72 | 0.36 | 22.0 % |

AI time per scan on the Kaggle GPU: 33 s on average (fastest 27 s, slowest 40 s, 10 scans); peak GPU memory 4.2 GB.

## Summary in seven sentences
RESULTS SUMMARY - CT Anatomy Explorer v0.5 (public TotalSegmentator CT scans)
Scans processed: 10 of 10 finished on a free Kaggle T4 GPU.
Time per scan: 27 to 40 seconds. Peak GPU memory: 4334 MB.
Average Dice over all organs and scans: 0.89.
Best organ: Liver (average Dice 0.97).
Weakest organ: Duodenum (average Dice 0.72).
Note: Dice shows agreement with expert masks on public data, not clinical accuracy.

## Files attached to this release
- web_data_final.zip: the scan and outline files used by the website
- organ_summary.csv: organ results aggregated over all 10 processed scans
- Results_Summary_v0.5.docx: the one-page results summary
- CT_Anatomy_Explorer_v0.5_demo.mp4: the demo video

## Credits and licences
- Data: TotalSegmentator dataset (Wasserthal et al., Radiology: Artificial Intelligence, 2023), Zenodo record 10047263, CC BY 4.0
- AI model: VISTA-3D MONAI bundle (MONAI/vista3d 0.5.11); NVIDIA licence: research and evaluation only, not for commercial use
- Viewer: NiiVue 0.69.0
- Team: Guna Rithvick and Ayushi N
