
#git reset --soft HEAD~1
git rm --cached Sargon-NNUE/data/pb/zod.pb
git rm --cached Sargon-NNUE/data/pb/zod_sample.pb
git rm --cached Sargon-NNUE/data/runs/lczero/t1-512x15x8h-distilled-swa-3395000.pb.gz
git rm --cached Sargon-NNUE/data/pb/boot.pb
git rm --cached Sargon-NNUE/data/pb/lex.pb

#git filter-branch --force --index-filter `
#"git rm --cached --ignore-unmatch Sargon-NNUE/data/pb/*.pb Sargon-NNUE/data/runs/lczero/*.gz" `
#--prune-empty --tag-name-filter cat -- --all

