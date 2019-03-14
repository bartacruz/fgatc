$(document).ready(function() {
        $('#main-navbar a').each(function(id,node){
                if (node.pathname == "{{ request.path}}" && !node.href.endsWith("#")) {
                        var qn = $(node);
                        qn.parent().addClass("active");
                        qn.parents('.dropdown').addClass("active");
                }
                
        });
        
});
