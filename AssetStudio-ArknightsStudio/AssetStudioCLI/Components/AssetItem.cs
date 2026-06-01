using Arknights;
using AssetStudio;

namespace AssetStudioCLI
{
    internal class AssetItem
    {
        public Object Asset;
        public SerializedFile SourceFile;
        public string Container = string.Empty;
        public string TypeString;
        public long m_PathID;
        public long FullSize;
        public ClassIDType Type;
        public string Text;
        public string UniqueID;
        public GameObjectNode Node;
        public PortraitSprite AkPortraitSprite;

        public AssetItem(Object asset)
        {
            Asset = asset;
            SourceFile = asset.assetsFile;
            Type = asset.type;
            TypeString = Type.ToString();
            m_PathID = asset.m_PathID;
            FullSize = asset.byteSize;
        }

        public AssetItem(PortraitSprite akPortraitSprite)
        {
            Asset = null;
            SourceFile = akPortraitSprite.AssetsFile;
            Container = akPortraitSprite.Container;
            Type = akPortraitSprite.Type;
            TypeString = Type.ToString();
            Text = akPortraitSprite.Name;
            m_PathID = -1;
            AkPortraitSprite = akPortraitSprite;
        }
    }
}
