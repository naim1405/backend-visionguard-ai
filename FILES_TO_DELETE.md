# Files to Delete After Verification

Once the STG-NF integration is verified to be working properly, the following old files can be safely deleted:

## Old AI Processing Files (DenseNet-based)

### Python Files
- `ai_service.py` - Old DenseNet anomaly detection service
- `ai_stream.py` - Old video stream without STG-NF pipeline

### Model Files
- `models/densenet_focal_epoch2.h5` - Old DenseNet model (97MB)

## Why These Can Be Deleted

The new STG-NF system completely replaces the old DenseNet system:

| Old System | New System |
|------------|------------|
| `ai_service.py` | `detection/` module |
| `ai_stream.py` | `ai_stream_stgnf.py` |
| DenseNet model | STG-NF model |
| No tracking | Deep SORT tracking |
| Single frame | 30-frame sequences |
| Image-based | Pose-based |

## Verification Checklist

Before deleting, verify:
- [ ] Backend starts without errors
- [ ] WebRTC connection works
- [ ] Video streams correctly
- [ ] Anomaly detection works
- [ ] Annotations appear on video
- [ ] Logs are written correctly
- [ ] No import errors for old modules

## Deletion Commands

Once verified, run:

```bash
cd /home/ezio/Documents/work/visiongaurd-backend

# Delete old Python files
rm ai_service.py
rm ai_stream.py

# Delete old model
rm models/densenet_focal_epoch2.h5

# Verify deletion
ls -lh ai_*.py
ls -lh models/
```

## Size Savings

Deleting these files will free up approximately:
- `ai_service.py`: ~2 KB
- `ai_stream.py`: ~3 KB
- `densenet_focal_epoch2.h5`: ~97 MB

**Total: ~97 MB**

## Backup Recommendation

Before deletion, consider creating a backup:

```bash
# Create backup directory
mkdir -p ~/backups/visiongaurd-old-system

# Backup old files
cp ai_service.py ~/backups/visiongaurd-old-system/
cp ai_stream.py ~/backups/visiongaurd-old-system/
cp models/densenet_focal_epoch2.h5 ~/backups/visiongaurd-old-system/
```

## Notes

- The old files are NOT imported or used by the new system
- Keeping them won't cause conflicts
- Delete only after thorough testing
- Keep backups if uncertain
