using AssetStudio;
using System.Collections.Generic;

namespace AssetStudioCLI
{
    internal class GameObjectNode : BaseNode
    {
        public GameObject gameObject;

        public GameObjectNode(GameObject gameObject)
        {
            this.gameObject = gameObject;
        }

    }
}
