using System.Windows.Forms;
using AssetStudio;
using Arknights;

namespace AssetStudioGUI
{
    internal class AssetItem : ListViewItem
    {
        public Object Asset;
        public SerializedFile SourceFile;
        public string Container = string.Empty;
        public string TypeString;
        public long m_PathID;
        public long FullSize;
        public ClassIDType Type;
        public string InfoText;
        public string UniqueID;
        public GameObjectTreeNode TreeNode;
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
            FullSize = (long)(akPortraitSprite.TextureRect.width * akPortraitSprite.TextureRect.height * 4);
            AkPortraitSprite = akPortraitSprite;
        }

        public void SetSubItems()
        {
            SubItems.AddRange(new[]
            {
                Container, //Container
                TypeString, //Type
                m_PathID.ToString(), //PathID
                FullSize.ToString(), //Size
            });
        }
    }
}
