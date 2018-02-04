function registerCollapsable() {
  $(".Collapsable").click(function () {
      console.log($(this));
      if ($(this).parent().hasClass('open')) {
        $(this).parent().removeClass('open')
        $(this).parent().addClass('closed')
      } else {
        $(this).parent().removeClass('closed')
        $(this).parent().addClass('open')
      }
  });
}
